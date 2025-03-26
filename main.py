#!/usr/bin/env python
import curses
from dataclasses import dataclass
from typing import Optional

import libdnf5


@dataclass
class ApplicationState:
    """Maintains the state of the curses application."""
    packages: list[str]
    base: str
    dependencies: set[str]
    selected_packages: set[str]
    viewing_dependencies: bool = False
    current_row: int = 0
    top_row: int = 0
    parent_package: Optional[str] = None


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
    _init_curses()

    state = ApplicationState(
        packages=get_user_installed_packages(base),
        dependencies=set(),
        selected_packages=set(),
        viewing_dependencies=False,
        current_row=0,
        top_row=0, base=base)

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Calculate the number of rows to display
        num_rows = min(len(state.packages) - state.top_row, height)

        if state.viewing_dependencies:
            display_packages = state.dependencies
            title = f"Dependencies required by {state.parent_package} (← to go back)"
        else:
            display_packages = state.packages
            title = "User-installed Packages (→ to view required dependencies)"

        for i in range(num_rows):
            idx = state.top_row + i
            package = display_packages[idx]

            marker = "[*] " if package in state.selected_packages else "[ ] "
            display_text = marker + package
            if len(display_text) > width - 2:
                display_text = display_text[: width - 5] + "..."

            x, y = 0, i

            if idx == state.current_row:
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(y, x, display_text)
                stdscr.attroff(curses.color_pair(1))
            else:
                stdscr.addstr(y, x, display_text)

        stdscr.refresh()

        key = stdscr.getch()

        # Navigation (Vim-style and arrow keys)
        if key in (ord("k"), curses.KEY_UP) and state.current_row > 0:
            state.current_row -= 1
            if state.current_row < state.top_row:
                state.top_row = state.current_row
        elif key in (ord("j"), curses.KEY_DOWN) and state.current_row < len(state.packages) - 1:
            state.current_row += 1
            if state.current_row >= state.top_row + height - 1:
                state.top_row = state.current_row - height + 2
        elif key == curses.KEY_PPAGE:  # Page Up
            state.current_row = max(0, state.current_row - height + 1)
            state.top_row = max(0, state.top_row - height + 1)
        elif key == curses.KEY_NPAGE:  # Page Down
            state.current_row = min(len(display_packages) - 1, state.current_row + height - 1)
            state.top_row = min(len(display_packages) - height + 1, state.top_row + height - 1)

        # Vim-style "gg" (go to top) and "G" (go to bottom)
        elif key == ord("g"):
            key2 = stdscr.getch()
            if key2 == ord("g"):
                _go_to_top(state)
        elif key == ord("G"):
            _go_to_bottom(state, height, total_items=len(display_packages))

        # Select/deselect with Space
        elif key == ord(" "):
            package_to_toggle = state.packages[state.current_row]
            if package_to_toggle in state.selected_packages:
                state.selected_packages.remove(package_to_toggle)
            else:
                state.selected_packages.add(package_to_toggle)

        # Remove selected packages with "d"
        elif key == ord("d") and state.selected_packages:
            remove_packages(state.base, state.selected_packages)
            state.packages = get_user_installed_packages(state.base)
            state.selected_packages.clear()
            state.current_row = min(state.current_row, len(display_packages) - 1)
            state.top_row = max(0, min(state.top_row, len(display_packages) - height))

        # View required dependencies of the selected package (→)
        elif key == curses.KEY_RIGHT and not state.viewing_dependencies:
            state.parent_package = state.packages[state.current_row]
            state.dependencies = get_user_installed_dependencies(base, state.parent_package)

            if state.dependencies:
                state.viewing_dependencies = True
                state.current_row, state.top_row = 0, 0

        # Return to main list (←)
        elif key == curses.KEY_LEFT and state.viewing_dependencies:
            state.viewing_dependencies = False
            state.dependencies = []
            state.parent_package = None
            state.current_row, state.top_row = 0, 0

        # Quit with "q"
        elif key == ord("q"):
            break


def _init_curses():
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.curs_set(0)


def _page_up(state, height):
    """Handle page up navigation."""
    state['current_row'] = max(0, state['current_row'] - height + 1)
    state['top_row'] = max(0, state['top_row'] - height + 1)


def _page_down(state: ApplicationState, height, total_items):
    """Handle page down navigation."""
    state.current_row = min(total_items - 1, state.current_row + height - 1)
    state.top_row = min(total_items - height + 1, state.top_row + height - 1)


def _go_to_top(state: ApplicationState):
    """Handle 'gg' command (go to top)."""
    state.current_row = 0
    state.top_row = 0


def _go_to_bottom(state: ApplicationState, height, total_items):
    """Handle 'G' command (go to bottom)."""
    state.current_row = total_items - 1
    state.top_row = max(0, total_items - height + 1)


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
