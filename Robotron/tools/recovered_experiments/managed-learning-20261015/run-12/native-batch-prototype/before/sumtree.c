/* Exact scalar float64 parent recomputation. No reassociation or fast math. */
#include <stdint.h>

void robotron_sumtree_propagate(double *tree, int64_t index)
{
    int64_t parent = index >> 1;
    while (parent >= 1) {
        tree[parent] = tree[parent * 2] + tree[parent * 2 + 1];
        parent >>= 1;
    }
}

/* One pass, without a temporary fp16 gather. Neoverse V2 performs IEEE half
 * conversion in SIMD instructions. The compiler chooses the vector width;
 * no alignment assumption is made about individual rows. */
int robotron_gather_fp16_rows(const uint16_t *source, const int64_t *indices,
                             float *restrict output, int64_t rows, int64_t columns)
{
#if defined(ROBOTRON_NEOVERSE_V2) && defined(__aarch64__)
    for (int64_t row = 0; row < rows; ++row) {
        const _Float16 *input = (const _Float16 *)(source + indices[row] * columns);
        float *destination = output + row * columns;
        for (int64_t column = 0; column < columns; ++column) {
            destination[column] = (float)input[column];
        }
    }
    return 1;
#else
    (void)source;
    (void)indices;
    (void)output;
    (void)rows;
    (void)columns;
    return 0;
#endif
}
