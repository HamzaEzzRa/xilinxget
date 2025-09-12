# Xilinx Download Crawler
Python script to automate the process of downloading tools from the AMD Xilinx website, without the need of a GUI. This script takes care of finding a specific tool/version, signing in, filling necessary information and saving the files locally.

## Prerequisites
**This was tested on Ubuntu 20.04, using Python 3.10.5**

To setup the environment, first update your packages:
```bash
sudo apt-get update
sudo apt-get upgrade
```

Install Google Chrome:
```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt-get install -y ./google-chrome-stable_current_amd64.deb
```

Install the following packages, creating a virtual env is recommended:
```bash
pip install selenium webdriver-manager
```

## Usage
Once the prerequisites are installed, you can run the script to choose and download a specific version of a tool.

### Command-line Usage
You can simply run the script from a terminal to choose from all available tools and versions:
```python
python main.py
```

You can pass more options for an advanced usage. Please check using "-h" option for further details:
```python
python main.py -h
```

## License
This project is licensed under the MIT License. See the LICENSE file for details.
