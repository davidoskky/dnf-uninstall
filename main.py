#!/usr/bin/env python
import curses
import subprocess
import libdnf5


def get_user_installed_packages(base):
    """
    Returns a list of user-installed packages.
    """
    package_query = libdnf5.rpm.PackageQuery(base)
    package_query.filter_userinstalled()
    package_query.filter_leaves()

    return [pkg.get_nevra() for pkg in package_query]


def get_user_installed_dependencies(base, package_name):
    """
    Returns a list of dependencies that are also user-installed.
    """
    package_query = libdnf5.rpm.PackageQuery(base)
    package_query.filter_installed()
    package_query.filter_name(package_name)

    if package_query.size() == 0:
        return []

    dependencies = set()
    for pkg in package_query:
        dep_query = libdnf5.rpm.PackageQuery(base)
        dep_query.filter_userinstalled()
        dep_query.filter_provides(pkg)

        dependencies.update([dep.get_nevra() for dep in dep_query])

    return sorted(dependencies)


def remove_packages(base, packages_to_remove):
    """
    Removes selected packages using libdnf5 transactions.
    """
    if not packages_to_remove:
        return

    goal = libdnf5.base.Goal(base)
    for package in packages_to_remove:
        goal.add_rpm_reason_change(
            package, libdnf5.transaction.TransactionItemReason_DEPENDENCY
        )
    transaction = goal.resolve()
    transaction.run()


def remove_package(base, package_name):
    """
    Marks the package as a dependency and removes it using libdnf5 transactions.
    """
    goal = libdnf5.base.Goal(base)
    goal.add_rpm_reason_change(
        package_name, libdnf5.transaction.TransactionItemReason_DEPENDENCY
    )
    transaction = goal.resolve()
    transaction.run()


def autoremove(base):
    """
    Removes unneeded packages."""
    unneeded = libdnf5.rpm.PackageQuery(base)
    unneeded.filter_unneeded()
    goal = libdnf5.base.Goal(base)

    for pkg in unneeded:
        print(f"Package removed: {pkg.get_nevra()}")
        goal.add_remove(pkg.get_nevra())

    transaction = goal.resolve()
    transaction.run()


def curses_main(stdscr, base):
    # Initialize color pair
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.curs_set(0)

    packages = get_user_installed_packages(base)
    dependencies = set()
    selected_packages = set()
    viewing_dependencies = False
    current_row = 0
    top_row = 0

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Calculate the number of rows to display
        num_rows = min(len(packages) - top_row, height)

        if viewing_dependencies:
            display_packages = dependencies
            title = f"Dependencies required by {parent_package} (← to go back)"
        else:
            display_packages = packages
            title = "User-installed Packages (→ to view required dependencies)"

        for i in range(num_rows):
            idx = top_row + i
            package = display_packages[idx]

            marker = "[*] " if package in selected_packages else "[ ] "
            display_text = marker + package
            if len(display_text) > width - 2:
                display_text = display_text[: width - 5] + "..."

            x, y = 0, i

            if idx == current_row:
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(y, x, display_text)
                stdscr.attroff(curses.color_pair(1))
            else:
                stdscr.addstr(y, x, display_text)

        stdscr.refresh()

        key = stdscr.getch()

        # Navigation (Vim-style and arrow keys)
        if key in (ord("k"), curses.KEY_UP) and current_row > 0:
            current_row -= 1
            if current_row < top_row:
                top_row = current_row
        elif key in (ord("j"), curses.KEY_DOWN) and current_row < len(packages) - 1:
            current_row += 1
            if current_row >= top_row + height - 1:
                top_row = current_row - height + 2
        elif key == curses.KEY_PPAGE:  # Page Up
            current_row = max(0, current_row - height + 1)
            top_row = max(0, top_row - height + 1)
        elif key == curses.KEY_NPAGE:  # Page Down
            current_row = min(len(display_packages) - 1, current_row + height - 1)
            top_row = min(len(display_packages) - height + 1, top_row + height - 1)

        # Vim-style "gg" (go to top) and "G" (go to bottom)
        elif key == ord("g"):
            key2 = stdscr.getch()
            if key2 == ord("g"):
                current_row = 0
                top_row = 0
        elif key == ord("G"):
            current_row = len(display_packages) - 1
            top_row = max(0, len(display_packages) - height + 1)

        # Select/deselect with Space
        elif key == ord(" "):
            package_to_toggle = packages[current_row]
            if package_to_toggle in selected_packages:
                selected_packages.remove(package_to_toggle)
            else:
                selected_packages.add(package_to_toggle)

        # Remove selected packages with "d"
        elif key == ord("d") and selected_packages:
            remove_packages(base, selected_packages)
            packages = get_user_installed_packages(base)
            selected_packages.clear()
            current_row = min(current_row, len(display_packages) - 1)
            top_row = max(0, min(top_row, len(display_packages) - height))

        # View required dependencies of the selected package (→)
        elif key == curses.KEY_RIGHT and not viewing_dependencies:
            parent_package = packages[current_row]
            dependencies = get_user_installed_dependencies(base, parent_package)

            if dependencies:
                viewing_dependencies = True
                current_row, top_row = 0, 0

        # Return to main list (←)
        elif key == curses.KEY_LEFT and viewing_dependencies:
            viewing_dependencies = False
            dependencies = []
            parent_package = None
            current_row, top_row = 0, 0

        # Quit with "q"
        elif key == ord("q"):
            break


if __name__ == "__main__":
    # Initialize libdnf5 Base
    base = libdnf5.base.Base()
    base.load_config()
    base.setup()

    repo_sack = base.get_repo_sack()
    repo_sack.create_repos_from_system_configuration()

    repo_sack.load_repos()

    curses.wrapper(lambda stdscr: curses_main(stdscr, base))

    autoremove(base)
