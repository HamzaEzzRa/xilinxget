# xilinxget
CLI tool to automate the process of downloading tools from the AMD Xilinx website, without the need of a GUI. The script takes care of finding a specific tool/version, signing in, filling necessary information and saving the files locally.

## Prerequisites
**This was tested on Ubuntu 20.04, using Python 3.10.5**

To setup the environment, first update your packages:
```bash
sudo apt update
sudo apt upgrade
```

Install Google Chrome:
```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb
```

Install Xvfb for virtual display:
```bash
sudo apt install xvfb
```

If you have [uv](https://docs.astral.sh/uv/) installed, simply skip to [Usage](#usage) section since uv will create a virtual env and install python dependencies for you on the first run.

Otherwise, install the following python dependencies with your package manager. A virtual env is recommended:
- pyvirtualdisplay
- selenium
- undetected-chromedriver

## Usage
Once the prerequisites are installed, you can run the script to choose and download a specific version of a tool.

### Command-line Usage
You can simply run the script from a terminal to choose from all available tools and versions.

Using uv:
```bash
uv run xilinxget
```

Or using the virtual environment:
```bash
xilinxget
```

You can pass more options for an advanced usage. Please check using "-h" option for further details:
```bash
xilinxget -h
```

For example, you can list all available tools and their versions, then pick a specific tool/version to download directly without the verbose list of all downloads:
```bash
xilinxget --list-tools
xilinxget --tool Vivado --version "Vivado Archive 2020.3"
```

## License
This project is licensed under the MIT License. See the LICENSE file for details.
