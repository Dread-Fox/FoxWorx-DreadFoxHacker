"""Child-only launcher: establish a controlling terminal before exec, without preexec_fn."""
import fcntl
import os
import sys
import termios

if __name__ == '__main__':
    os.setsid()
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    os.execvpe(sys.argv[1], sys.argv[1:], os.environ)
