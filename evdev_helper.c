#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <linux/input.h>

static volatile sig_atomic_t keep_running = 1;

static void handle_signal(int sig) {
    (void)sig;
    keep_running = 0;
}

int main(int argc, char *argv[]) {
    const char *dev_path = NULL;
    int target_code = 0;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--device") == 0 && i + 1 < argc)
            dev_path = argv[++i];
        else if (strcmp(argv[i], "--keycode") == 0 && i + 1 < argc)
            target_code = atoi(argv[++i]);
    }

    if (!dev_path || target_code <= 0) {
        fprintf(stderr, "Usage: evdev_helper --device <path> --keycode <num>\n");
        return 1;
    }

    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = handle_signal;
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);
    signal(SIGPIPE, SIG_DFL);

    int fd = open(dev_path, O_RDONLY);
    if (fd < 0) {
        perror("open");
        return 1;
    }

    struct input_event ev;
    char buf[128];
    int n;

    while (keep_running && (n = read(fd, &ev, sizeof(ev))) == sizeof(ev)) {
        if (ev.type == EV_KEY && ev.code == target_code) {
            if (ev.value == 1) {
                n = snprintf(buf, sizeof(buf),
                    "{\"key\":%d,\"state\":\"down\"}\n", ev.code);
                if (write(STDOUT_FILENO, buf, n) < 0) break;
            } else if (ev.value == 0) {
                n = snprintf(buf, sizeof(buf),
                    "{\"key\":%d,\"state\":\"up\"}\n", ev.code);
                if (write(STDOUT_FILENO, buf, n) < 0) break;
            }
        }
    }

    close(fd);
    return 0;
}
