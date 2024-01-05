#!/usr/bin/env python
import curses
import subprocess

def get_user_installed_packages():
    result = subprocess.run(['dnf', 'repoquery', '--userinstalled'], stdout=subprocess.PIPE)
    packages = result.stdout.decode('utf-8').split('\n')
    return packages

def curses_main(stdscr):
    # Initialize color pair
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.curs_set(0)

    packages = get_user_installed_packages()

    current_row = 0
    top_row = 0

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Calculate the number of rows to display
        num_rows = min(len(packages) - top_row, height)

        for i in range(num_rows):
            idx = top_row + i
            package = packages[idx]

            if len(package) > width - 2:
                package = package[:width - 5] + '...'

            x = 0
            y = i

            if idx == current_row:
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(y, x, package)
                stdscr.attroff(curses.color_pair(1))
            else:
                stdscr.addstr(y, x, package)

        stdscr.refresh()

        key = stdscr.getch()

        if key == curses.KEY_UP and current_row > 0:
            current_row -= 1
            if current_row < top_row:
                top_row = current_row
        elif key == curses.KEY_DOWN and current_row < len(packages) - 1:
            current_row += 1
            if current_row >= top_row + height:
                top_row = current_row - height + 1
        elif key == ord('q'):
            break
        elif key == ord('d'):
            package_to_remove = packages[current_row]
            subprocess.run(['sudo', 'dnf', 'mark', 'remove', package_to_remove])

            packages = get_user_installed_packages()
            current_row = max(0, min(current_row, len(packages) - 1))  # Reset selection
            top_row = max(0, min(top_row, len(packages) - height))

    curses.endwin()


if __name__ == '__main__':
    curses.wrapper(curses_main)
    subprocess.run(['sudo', 'dnf', 'autoremove'])

