/* Offline prototype: exact level-snapshot SumTree batch propagation. */
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>

static int compare_index(const void *a, const void *b)
{
    const int64_t left = *(const int64_t *)a;
    const int64_t right = *(const int64_t *)b;
    return (left > right) - (left < right);
}

/* Return zero only before any mutation, so the caller can use its old path. */
int robotron_sumtree_batch_update(double *tree, int64_t tree_size,
                                 int64_t capacity, const int64_t *indices,
                                 const double *priorities, int64_t count)
{
    if (!tree || !indices || !priorities || count <= 0 || capacity <= 0
            || capacity > INT64_MAX / 2 || tree_size != 2 * capacity
            || (uint64_t)count > SIZE_MAX / sizeof(int64_t)
            || (uint64_t)count > SIZE_MAX / sizeof(double)) return 0;
    for (int64_t i = 0; i < count; ++i)
        if (indices[i] < 0 || indices[i] >= capacity) return 0;
    int64_t *parents = malloc((size_t)count * sizeof(int64_t));
    double *sums = malloc((size_t)count * sizeof(double));
    if (!parents || !sums) {
        free(parents);
        free(sums);
        return 0;
    }
    /* Ordered leaf assignment exactly matches the observed NumPy oracle. */
    for (int64_t i = 0; i < count; ++i) {
        const int64_t leaf = indices[i] + capacity;
        tree[leaf] = priorities[i];
        parents[i] = leaf >> 1;
    }
    qsort(parents, (size_t)count, sizeof(int64_t), compare_index);
    int64_t unique = 0;
    for (int64_t i = 0; i < count; ++i)
        if (unique == 0 || parents[i] != parents[unique - 1])
            parents[unique++] = parents[i];
    while (unique > 0 && parents[0] >= 1) {
        /* An odd/non-power capacity can put ancestor+child in one level.
         * NumPy gathers the complete RHS before assigning ANY parent. */
        for (int64_t i = 0; i < unique; ++i) {
            const int64_t parent = parents[i];
            sums[i] = tree[parent * 2] + tree[parent * 2 + 1];
        }
        for (int64_t i = 0; i < unique; ++i) tree[parents[i]] = sums[i];
        int64_t next = 0;
        for (int64_t i = 0; i < unique; ++i) {
            const int64_t parent = parents[i] >> 1;
            if (parent >= 1 && (next == 0 || parent != parents[next - 1]))
                parents[next++] = parent;
        }
        unique = next;
    }
    free(sums);
    free(parents);
    return 1;
}
