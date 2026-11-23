/* Which triangles of a model can be seen: a small software rasterizer for
 * optimize_gltf.py.
 *
 *     visibility <tris.bin> <out.vis> < commands
 *
 * tris.bin: int32 n, then n * 9 float32 (three corners a triangle), then n int32 flags
 * (bit 0: the triangle hides nothing, as glass or a cut-out decal). Commands, one a line:
 *
 *     P w h ex ey ez tx ty tz fov    a camera at e looking at t, vertical fov in degrees
 *     C res ex ey ez                 all six directions from a point
 *     O res dx dy dz cx cy cz width  from far outside, looking along d at c
 *     B res ex ey ez                 prints the share of what a point sees, all six
 *                                    directions, that shows its back: high inside a solid
 *
 * out.vis: n bytes, bit 0 where a triangle is the nearest surface at some pixel of a P or
 * C view (or, too small to hold a pixel, within a pixel of one), bit 1 in an O view. Each view prints a hash of its depth picture, so a caller
 * can check that a model with triangles taken out draws the same depth everywhere.
 */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HAIR 1e-4 /* metres: nearer than this behind the nearest surface is on it */

#define FINE 1e-3 /* metres */

typedef struct { double x, y, z; } V;
static int n, W, H, bit;
static float *T, *zb;
static unsigned char *fb; /* per pixel: 1 where the nearest surface shows its back */
static int *F;
static unsigned char *vis;

static V sub(V a, V b) { return (V){a.x - b.x, a.y - b.y, a.z - b.z}; }
static V cross(V a, V b) { return (V){a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x}; }
static double dot(V a, V b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
static V norm(V a) { double l = sqrt(dot(a, a)); return (V){a.x / l, a.y / l, a.z / l}; }

static void setup(int w, int h) {
    W = w; H = h;
    if (w <= 0 || h <= 0) exit(2);
    zb = realloc(zb, sizeof(float) * w * h);
    fb = realloc(fb, (size_t)w * h);
    if (!zb || !fb) exit(2);
    for (int i = 0; i < w * h; i++) zb[i] = 0;
}

static V E, R, U, Fw;
static double focal, oscale;
static int ortho;

/* A triangle on the screen: pixels, and q = 1 / depth, larger nearer. With `test` 0 it
 * is drawn into the depth picture. With `test` 1 it is judged against the finished one:
 * seen if it is the nearest surface at a pixel centre inside it. One too small or too
 * thin to hold a pixel centre is judged at the centres within a pixel of it, so it is
 * not missed. */
static void fill(const double *x, const double *y, const double *q, int id, int test) {
    double a = (x[1] - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (y[1] - y[0]);
    if (fabs(a) < 1e-12) return;
    int grow = test ? 1 : 0;
    int x0 = (int)floor(fmin(x[0], fmin(x[1], x[2]))) - grow, x1 = (int)ceil(fmax(x[0], fmax(x[1], x[2]))) + grow;
    int y0 = (int)floor(fmin(y[0], fmin(y[1], y[2]))) - grow, y1 = (int)ceil(fmax(y[0], fmax(y[1], y[2]))) + grow;
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 > W - 1) x1 = W - 1;
    if (y1 > H - 1) y1 = H - 1;
    double ia = 1.0 / a;
    double qmin = fmin(q[0], fmin(q[1], q[2])), qmax = fmax(q[0], fmax(q[1], q[2]));
    /* 0: draw. 1: judge at the pixel centres inside. 2: none was inside, so judge at the
     * centres within a pixel of it, by the depth it has nearest there. */
    for (int pass = test; pass <= 2 * test; pass++) {
        double slack[3] = {0, 0, 0};
        int inside = 0;
        if (pass == 2) {
            /* Only where a pixel is finer than FINE on it: from far off, everything is
             * within a pixel of something nearer, and a nearer view judges it better. */
            if (ortho || 1 / (qmax * focal) > FINE) return;
            for (int k = 0; k < 3; k++) {
                int i = (k + 1) % 3, j = (k + 2) % 3;
                slack[k] = hypot(x[j] - x[i], y[j] - y[i]) / fabs(a);
            }
        }
        for (int py = y0; py <= y1; py++) {
            double cy = py + 0.5;
            for (int px = x0; px <= x1; px++) {
                double cx = px + 0.5;
                double w0 = ((x[1] - cx) * (y[2] - cy) - (x[2] - cx) * (y[1] - cy)) * ia;
                double w1 = ((x[2] - cx) * (y[0] - cy) - (x[0] - cx) * (y[2] - cy)) * ia;
                double w2 = 1 - w0 - w1;
                if (w0 < -slack[0] || w1 < -slack[1] || w2 < -slack[2]) continue;
                double d = w0 * q[0] + w1 * q[1] + w2 * q[2];
                int k = py * W + px;
                if (pass == 0) {
                    /* The screen's y runs down, so a front face winds with a < 0. */
                    if ((float)d > zb[k]) { zb[k] = (float)d; fb[k] = a > 0; }
                    continue;
                }
                inside = 1;
                if (pass == 1 ? (float)d >= zb[k] : zb[k] > 0 && 1 / fmin(fmax(d, qmin), qmax) <= 1 / (double)zb[k] + HAIR) {
                    vis[id] |= bit;
                    return;
                }
            }
        }
        if (inside) return;
    }
}


static void look(V e, V t, V up) {
    E = e;
    Fw = norm(sub(t, e));
    R = norm(cross(Fw, up));
    U = cross(R, Fw);
}

static void draw(int test) {
    const double near = 0.01;
    for (int i = 0; i < n; i++) {
        if (F[i] & 1) continue;
        V p[3];
        for (int k = 0; k < 3; k++) {
            V d = sub((V){T[i * 9 + k * 3], T[i * 9 + k * 3 + 1], T[i * 9 + k * 3 + 2]}, E);
            p[k] = (V){dot(d, R), dot(d, U), dot(d, Fw)};
        }
        double sx[4], sy[4], q[4];
        if (ortho) {
            for (int k = 0; k < 3; k++) {
                sx[k] = W / 2 + p[k].x * oscale;
                sy[k] = H / 2 - p[k].y * oscale;
                q[k] = 1.0 / p[k].z;
            }
            fill(sx, sy, q, i, test);
            continue;
        }
        V poly[4];
        int m = 0;
        for (int k = 0; k < 3; k++) {
            V a = p[k], b = p[(k + 1) % 3];
            int in_a = a.z >= near, in_b = b.z >= near;
            if (in_a) poly[m++] = a;
            if (in_a != in_b) {
                double t = (near - a.z) / (b.z - a.z);
                poly[m++] = (V){a.x + t * (b.x - a.x), a.y + t * (b.y - a.y), near};
            }
        }
        if (m < 3) continue;
        for (int k = 0; k < m; k++) {
            sx[k] = W / 2 + poly[k].x / poly[k].z * focal;
            sy[k] = H / 2 - poly[k].y / poly[k].z * focal;
            q[k] = 1.0 / poly[k].z;
        }
        for (int k = 1; k + 1 < m; k++) {
            double tx[3] = {sx[0], sx[k], sx[k + 1]}, ty[3] = {sy[0], sy[k], sy[k + 1]};
            double tq[3] = {q[0], q[k], q[k + 1]};
            fill(tx, ty, tq, i, test);
        }
    }
}

/* Draws the view, marks what it shows with `as`, and prints its depth picture's hash. */
static void view(int as, const char *what) {
    draw(0);
    bit = as;
    draw(1);
    uint64_t h = 1469598103934665603ull;
    for (int k = 0; k < W * H; k++) {
        uint32_t u;
        memcpy(&u, &zb[k], 4);
        h = (h ^ u) * 1099511628211ull;
    }
    printf("%s %016llx\n", what, (unsigned long long)h);
}

int main(int argc, char **argv) {
    if (argc < 3) return 2;
    FILE *f = fopen(argv[1], "rb");
    if (!f || fread(&n, 4, 1, f) != 1 || n <= 0) return 2;
    T = malloc(36 * (size_t)n);
    F = malloc(4 * (size_t)n);
    vis = calloc(n, 1);
    if (!T || !F || !vis) return 2;
    if (fread(T, 36, n, f) != (size_t)n || fread(F, 4, n, f) != (size_t)n) return 2;
    fclose(f);
    char cmd[8];
    while (scanf("%7s", cmd) == 1) {
        double a[7];
        int w, h;
        if (cmd[0] == 'P') {
            if (scanf("%d %d %lf %lf %lf %lf %lf %lf %lf", &w, &h, &a[0], &a[1], &a[2], &a[3], &a[4], &a[5], &a[6]) != 9) return 2;
            setup(w, h);
            ortho = 0;
            focal = h * 0.5 / tan(a[6] * M_PI / 360);
            look((V){a[0], a[1], a[2]}, (V){a[3], a[4], a[5]}, (V){0, 1, 0});
            view(1, "P");
        } else if (cmd[0] == 'C') {
            if (scanf("%d %lf %lf %lf", &w, &a[0], &a[1], &a[2]) != 4) return 2;
            V dirs[6] = {{1, 0, 0}, {-1, 0, 0}, {0, 1, 0}, {0, -1, 0}, {0, 0, 1}, {0, 0, -1}};
            V ups[6] = {{0, 1, 0}, {0, 1, 0}, {0, 0, 1}, {0, 0, -1}, {0, 1, 0}, {0, 1, 0}};
            for (int d = 0; d < 6; d++) {
                setup(w, w);
                ortho = 0;
                focal = w * 0.5 * 0.98; /* a little over 90 degrees, so the faces overlap */
                V e = {a[0], a[1], a[2]};
                look(e, (V){e.x + dirs[d].x, e.y + dirs[d].y, e.z + dirs[d].z}, ups[d]);
                view(1, "C");
            }
        } else if (cmd[0] == 'B') {
            if (scanf("%d %lf %lf %lf", &w, &a[0], &a[1], &a[2]) != 4) return 2;
            V dirs[6] = {{1, 0, 0}, {-1, 0, 0}, {0, 1, 0}, {0, -1, 0}, {0, 0, 1}, {0, 0, -1}};
            V ups[6] = {{0, 1, 0}, {0, 1, 0}, {0, 0, 1}, {0, 0, -1}, {0, 1, 0}, {0, 1, 0}};
            long hit = 0, back = 0;
            for (int d = 0; d < 6; d++) {
                setup(w, w);
                ortho = 0;
                focal = w * 0.5;
                V e = {a[0], a[1], a[2]};
                look(e, (V){e.x + dirs[d].x, e.y + dirs[d].y, e.z + dirs[d].z}, ups[d]);
                draw(0);
                for (int k = 0; k < w * w; k++)
                    if (zb[k] > 0) { hit++; back += fb[k]; }
            }
            printf("B %f\n", hit ? (double)back / hit : 0.0);
        } else if (cmd[0] == 'O') {
            if (scanf("%d %lf %lf %lf %lf %lf %lf %lf", &w, &a[0], &a[1], &a[2], &a[3], &a[4], &a[5], &a[6]) != 8) return 2;
            setup(w, w);
            ortho = 1;
            oscale = w / a[6]; /* a[6]: the width seen, in metres */
            V d = norm((V){a[0], a[1], a[2]}), c = {a[3], a[4], a[5]};
            look((V){c.x - d.x * 50, c.y - d.y * 50, c.z - d.z * 50}, c, fabs(d.y) > 0.95 ? (V){0, 0, 1} : (V){0, 1, 0});
            view(2, "O");
        }
    }
    f = fopen(argv[2], "wb");
    if (!f || fwrite(vis, 1, n, f) != (size_t)n || fclose(f) != 0) return 2;
    return 0;
}
