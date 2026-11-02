/* Opt-in readiness waiting for MAME's zero-timeout TCP receive polling.
 *
 * The preload changes only a single readable-fd poll for a connected TCP peer
 * on the configured training port. A ready socket still returns immediately.
 * All other select calls retain their original arguments and libc behavior.
 */
#define _GNU_SOURCE

#include <arpa/inet.h>
#include <dlfcn.h>
#include <errno.h>
#include <netinet/in.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>

typedef int (*select_function)(int, fd_set *, fd_set *, fd_set *, struct timeval *);
static select_function libc_select;
static pthread_once_t initialize_once = PTHREAD_ONCE_INIT;
static unsigned int wait_us;
static unsigned int peer_port;
static atomic_uchar logged_fds[FD_SETSIZE];

/* Reject signs, spaces, suffixes, overflow and out-of-range settings. */
static int parse_decimal(const char *text, unsigned int maximum, unsigned int *value)
{
    unsigned int result = 0;
    if (text == NULL || *text == '\0')
        return 0;
    for (; *text != '\0'; ++text) {
        unsigned int digit;
        if (*text < '0' || *text > '9')
            return 0;
        digit = (unsigned int)(*text - '0');
        if (result > (maximum - digit) / 10)
            return 0;
        result = result * 10 + digit;
        if (result > maximum)
            return 0;
    }
    *value = result;
    return 1;
}

static void initialize(void)
{
    const char *port_text;
    void *symbol;
    int saved_errno = errno;

    /* An inherited marker must never advertise a disabled or failed load. */
    unsetenv("ROBOTRON_SOCKET_WAIT_ACTIVE");
    symbol = dlsym(RTLD_NEXT, "select");
    /* POSIX specifies dlsym's function-address conversion. */
    *(void **)(&libc_select) = symbol;
    if (libc_select == NULL)
        goto finished;
    if (!parse_decimal(getenv("ROBOTRON_SOCKET_WAIT_US"), 10000, &wait_us)
            || wait_us == 0)
        goto disabled;
    port_text = getenv("ROBOTRON_SOCKET_WAIT_PORT");
    peer_port = 9998;
    if (port_text != NULL
            && (!parse_decimal(port_text, 65535, &peer_port) || peer_port == 0))
        goto disabled;
    if (setenv("ROBOTRON_SOCKET_WAIT_ACTIVE", "select-v1", 1) != 0)
        goto disabled;
    goto finished;
disabled:
    wait_us = 0;
finished:
    errno = saved_errno;
}

__attribute__((constructor)) static void initialize_preload(void)
{
    pthread_once(&initialize_once, initialize);
}

static int target_fd(int nfds, const fd_set *readfds)
{
    int candidate = -1;
    int socket_type;
    int socket_protocol;
    socklen_t type_size = sizeof(socket_type);
    socklen_t protocol_size = sizeof(socket_protocol);
    struct sockaddr_storage peer;
    socklen_t peer_size = sizeof(peer);
    unsigned int port;

    if (nfds <= 0 || nfds > FD_SETSIZE || readfds == NULL)
        return -1;
    for (int fd = 0; fd < nfds; ++fd) {
        if (!FD_ISSET(fd, readfds))
            continue;
        if (candidate != -1)
            return -1;
        candidate = fd;
    }
    if (candidate < 0
            || getsockopt(candidate, SOL_SOCKET, SO_TYPE, &socket_type, &type_size) < 0
            || socket_type != SOCK_STREAM
            || getsockopt(candidate, SOL_SOCKET, SO_PROTOCOL, &socket_protocol, &protocol_size) < 0
            || socket_protocol != IPPROTO_TCP
            || getpeername(candidate, (struct sockaddr *)&peer, &peer_size) < 0)
        return -1;
    if (peer.ss_family == AF_INET)
        port = ntohs(((struct sockaddr_in *)&peer)->sin_port);
    else if (peer.ss_family == AF_INET6)
        port = ntohs(((struct sockaddr_in6 *)&peer)->sin6_port);
    else
        return -1;
    return port == peer_port ? candidate : -1;
}

int select(int nfds, fd_set *readfds, fd_set *writefds, fd_set *exceptfds,
           struct timeval *timeout)
{
    int saved_errno = errno;
    int fd = -1;
    pthread_once(&initialize_once, initialize);
    if (libc_select == NULL) {
        errno = ENOSYS;
        return -1;
    }
    if (wait_us != 0 && writefds == NULL && exceptfds == NULL
            && timeout != NULL && timeout->tv_sec == 0 && timeout->tv_usec == 0)
        fd = target_fd(nfds, readfds);
    if (fd >= 0) {
        struct timeval local_timeout = {0, (suseconds_t)wait_us};
        unsigned char expected = 0;
        if (atomic_compare_exchange_strong(&logged_fds[fd], &expected, 1)) {
            char message[160];
            int length = snprintf(message, sizeof(message),
                "[robotron-socket-wait] pid=%ld fd=%d port=%u interval_us=%u\n",
                (long)getpid(), fd, peer_port, wait_us);
            if (length > 0 && (size_t)length < sizeof(message)) {
                ssize_t written = write(STDERR_FILENO, message, (size_t)length);
                (void)written;
            }
        }
        errno = saved_errno;
        /* libc updates the caller's fd sets normally, but its zero timeval
         * stays zero even on timeout, signal interruption or other error. */
        return libc_select(nfds, readfds, NULL, NULL, &local_timeout);
    }
    errno = saved_errno;
    return libc_select(nfds, readfds, writefds, exceptfds, timeout);
}
