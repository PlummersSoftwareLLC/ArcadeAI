/* Host sleep for MAME's otherwise nonblocking Lua socket receive loop.
 *
 * This is a Lua C function without Lua API dependencies: it takes no Lua
 * arguments, returns no Lua values, and never dereferences lua_State. MAME can
 * load it with package.loadlib(path, "robotron_socket_wait"). Sleeping only
 * after an empty read leaves emulated time and received action bytes alone.
 */
#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <stdlib.h>
#include <time.h>

struct lua_State;

/* Read on each call so the library has no initialization or shared state.
 * Invalid values disable sleeping; valid integers are clamped to 0..10000 us.
 */
unsigned int robotron_socket_wait_us(void)
{
    const char *text = getenv("ROBOTRON_SOCKET_WAIT_US");
    char *end;
    long value;

    if (text == NULL || *text == '\0')
        return 0;
    errno = 0;
    value = strtol(text, &end, 10);
    if (errno == ERANGE || end == text || *end != '\0')
        return 0;
    if (value <= 0)
        return 0;
    return value > 10000 ? 10000U : (unsigned int)value;
}

int robotron_socket_wait(struct lua_State *state)
{
    unsigned int microseconds = robotron_socket_wait_us();
    struct timespec remaining;
    (void)state;

    if (microseconds == 0)
        return 0;
    remaining.tv_sec = 0;
    remaining.tv_nsec = (long)microseconds * 1000L;
    /* Preserve the bounded wait across a signal without spinning on errors. */
    while (nanosleep(&remaining, &remaining) < 0 && errno == EINTR) {
    }
    return 0;
}
