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
        top_row=0,
        base=base,
    )

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        _render_title(stdscr, state)
        _render_packages(stdscr, state, height, width)

        stdscr.refresh()

        key = stdscr.getch()

        # Navigation (Vim-style and arrow keys)
        if key in (ord("k"), curses.KEY_UP):
            _move_vertical(state, -1, height)
        elif key in (ord("j"), curses.KEY_DOWN):
            _move_vertical(state, 1, height)
        elif key == curses.KEY_PPAGE:
            _page_move(state, -height + 1)
        elif key == curses.KEY_NPAGE:
            _page_move(state, height - 1)
        elif key == ord("g") and stdscr.getch() == ord("g"):
            _go_to_top(state)
        elif key == ord("G"):
            _go_to_bottom(state, height)
        elif key == ord(" "):
            _toggle_selection(state)
        elif key == ord("d") and state.selected_packages:
            _remove_selected(state)
        elif key == curses.KEY_RIGHT and not state.viewing_dependencies:
            _view_dependencies(state)
        elif key == curses.KEY_LEFT and state.viewing_dependencies:
            _return_to_main(state)
        elif key == ord("q"):
            break


def _init_curses():
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.curs_set(0)


def _get_display_content(state: ApplicationState) -> list[str]:
    """Determine which packages and title to display."""
    if state.viewing_dependencies:
        return list(state.dependencies)
    return state.packages


def _render_title(stdscr, state: ApplicationState) -> None:
    """Render the screen title."""
    if state.viewing_dependencies:
        title = f"Dependencies required by {state.parent_package} (← to go back)"
    else:
        title = "User-installed Packages (→ to view required dependencies)"
    stdscr.addstr(0, 0, title, curses.color_pair(2))


def _render_packages(stdscr, state: ApplicationState, height: int, width: int) -> None:
    """Render the package list."""
    if state.viewing_dependencies:
        packages = state.dependencies
    else:
        packages = state.packages

    num_rows = min(len(packages) - state.top_row, height - 1)  # -1 for title

    for i in range(num_rows):
        idx = state.top_row + i
        package = packages[idx]
        _render_package_row(stdscr, i + 1, package, state, width, idx)


def _render_package_row(
    stdscr, row: int, package: str, state: ApplicationState, width: int, idx: int
) -> None:
    """Render a single package row."""
    marker = "[*] " if package in state.selected_packages else "[ ] "
    display_text = f"{marker}{package}"[: width - 5] + (
        "..." if len(marker + package) > width - 2 else ""
    )

    if idx == state.current_row:
        stdscr.attron(curses.color_pair(1))
        stdscr.addstr(row, 0, display_text)
        stdscr.attroff(curses.color_pair(1))
    else:
        stdscr.addstr(row, 0, display_text)


def _toggle_selection(state):
    pkg = state.packages[state.current_row]
    (
        state.selected_packages.remove(pkg)
        if pkg in state.selected_packages
        else state.selected_packages.add(pkg)
    )


def _remove_selected(state):
    remove_packages(state.base, state.selected_packages)
    state.packages = get_user_installed_packages(state.base)
    state.selected_packages.clear()
    state.current_row = min(state.current_row, len(state.packages) - 1)


def _move_vertical(state, delta, height):
    state.current_row = max(0, min(state.current_row + delta, len(state.packages) - 1))
    if state.current_row < state.top_row:
        state.top_row = state.current_row
    elif state.current_row >= state.top_row + height - 1:
        state.top_row = state.current_row - height + 2


def _page_move(state, delta):
    state.current_row = max(0, min(state.current_row + delta, len(state.packages) - 1))
    state.top_row = max(
        0, min(state.top_row + delta, len(state.packages) - (curses.LINES - 1))
    )


def _go_to_top(state: ApplicationState):
    """Handle 'gg' command (go to top)."""
    state.current_row = 0
    state.top_row = 0


def _go_to_bottom(state: ApplicationState, height):
    """Handle 'G' command (go to bottom)."""
    state.current_row = len(state.packages) - 1
    state.top_row = max(0, len(state.packages) - height + 1)


def _view_dependencies(state):
    state.parent_package = state.packages[state.current_row]
    state.dependencies = get_user_installed_dependencies(
        state.base, state.parent_package
    )
    if state.dependencies:
        state.viewing_dependencies = True
        _go_to_top(state)


def _return_to_main(state):
    state.viewing_dependencies = False
    state.dependencies.clear()
    state.parent_package = None
    _go_to_top(state)


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
