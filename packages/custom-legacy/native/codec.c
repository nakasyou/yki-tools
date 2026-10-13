#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "g722_1/g722_1.h"

int main(int argc, char **argv) {
    if (argc != 4 || (strcmp(argv[1], "encode") && strcmp(argv[1], "decode"))) return 2;
    int encoding = !strcmp(argv[1], "encode");
    FILE *f = fopen(argv[2], "rb");
    if (!f || fseek(f, 0, SEEK_END)) return 1;
    long n = ftell(f);
    int frame_bytes = encoding ? 640 : 40;
    if (n <= 0 || n % frame_bytes || n > 64000000 || fseek(f, 0, SEEK_SET)) return 1;
    size_t output_bytes = (size_t)(n / frame_bytes) * (encoding ? 40 : 640);
    uint8_t *input = malloc((size_t)n);
    uint8_t *output = malloc(output_bytes);
    if (!input || !output || fread(input, 1, (size_t)n, f) != (size_t)n) return 1;
    fclose(f);
    int count;
    if (encoding) {
        int16_t *pcm = malloc((size_t)n);
        if (!pcm) return 1;
        for (long i=0; i<n/2; ++i)
            pcm[i] = (int16_t)((uint16_t)input[2*i] | ((uint16_t)input[2*i+1]<<8));
        g722_1_encode_state_t *s = g722_1_encode_init(NULL,16000,16000);
        if (!s) return 1;
        count = g722_1_encode(s,output,pcm,(int)n/2);
        g722_1_encode_release(s);
        free(pcm);
    } else {
        int16_t *pcm = malloc(output_bytes);
        if (!pcm) return 1;
        g722_1_decode_state_t *s = g722_1_decode_init(NULL,16000,16000);
        if (!s) return 1;
        count = g722_1_decode(s,pcm,input,(int)n)*2;
        g722_1_decode_release(s);
        for (int i=0; i<count/2; ++i) {
            output[2*i] = (uint16_t)pcm[i]&255;
            output[2*i+1] = (uint16_t)pcm[i]>>8;
        }
        free(pcm);
    }
    if ((size_t)count != output_bytes) return 1;
    f = fopen(argv[3],"wb");
    if (!f) return 1;
    int ok = fwrite(output,1,output_bytes,f) == output_bytes;
    if (fclose(f)) ok = 0;
    free(input); free(output);
    return ok ? 0 : 1;
}
