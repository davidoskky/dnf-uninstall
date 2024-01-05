# DNF-Uninstall - TUI to uninstall dnf packages
## Introduction

DNF-Uninstall is a Python-based terminal user interface (TUI) to easily uninstall manually installed packages through the DNF package manager.
This tool simplifies the process of removing packages from your system while still keeping the ones which are required by other ones.
It uses the curses library to provide a user-friendly, interactive interface.
This is useful because through this process you ensure you're not uninstalling any package on which another package depends, but just mark it as automatically installed.

# Installation
## Prerequisites

    Python 3.x

## Setup

    Clone the repository:

    git clone https://github.com/davidoskky/dnf-uninstall.git

Link the script to your local binary folder

ln -s $(realpath dnf-uninstall/main.py) ~/.local/bin/dnf-uninstall

Key Commands

Arrow Up/Down: Navigate through the software list. D: Cancel mark the software to be removed. Q: Quit the application and remove the packages.
