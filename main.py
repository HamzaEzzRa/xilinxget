import argparse
import os
import re
import time
from getpass import getpass
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from pager import pager_print

global g_driver
g_driver = None


class SoftwareVersion:
    def __init__(self, v_str: str):
        if not re.match(r"^\d+\.\d+(\.\d+)?$", v_str):
            raise ValueError(
                "Invalid version format. Expected format: (0-9)+.(0-9)+ or (0-9)+.(0-9)+.(0-9)+ (e.g., 2024.1 or 2024.1.0)"
            )

        parts = v_str.split(".")

        self.major = int(parts[0])
        self.minor = int(parts[1])
        self.patch = int(parts[2]) if len(parts) == 3 else None

    def _validate_patch_comparison(self, other):
        if (self.patch is None) != (other.patch is None):
            raise ValueError("Cannot compare software versions where one has a patch and the other does not.")

    def __eq__(self, other):
        self._validate_patch_comparison(other) 
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __lt__(self, other):
        self._validate_patch_comparison(other) 
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other):
        self._validate_patch_comparison(other) 
        return (self.major, self.minor, self.patch) <= (other.major, other.minor, other.patch)

    def __gt__(self, other):
        self._validate_patch_comparison(other) 
        return (self.major, self.minor, self.patch) > (other.major, other.minor, other.patch)

    def __ge__(self, other):
        self._validate_patch_comparison(other) 
        return (self.major, self.minor, self.patch) >= (other.major, other.minor, other.patch)

    def __str__(self):
        if self.patch is None:
            return f"{self.major}.{self.minor}"

        return f"{self.major}.{self.minor}.{self.patch}"

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash(str(self))


def size_str_to_nbytes(size_str: str):
    match = re.match(r"(\d+(\.\d+)?)\s*(B|KB|MB|GB|TB|PB|EB|ZB|YB)", size_str)
    if not match:
        raise ValueError("Invalid size format. Expected format: (0-9)+.(0-9)+ (B|KB|MB|GB|TB|PB|EB|ZB|YB)")

    size_f, unit = float(match.group(1)), match.group(3)
    size_units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")

    return int(size_f * 10 ** (size_units.index(unit) * 3))


def format_tool_name(name: str):
    formatted = ''
    skip1c = 0
    skip2c = 0
    for i in name:
        if i == '[':
            skip1c += 1
        elif i == '(':
            skip2c += 1
        elif i == ']' and skip1c > 0:
            skip1c -= 1
        elif i == ')'and skip2c > 0:
            skip2c -= 1
        elif skip1c == 0 and skip2c == 0:
            formatted += i
    return formatted.strip()


def get_chrome_driver(download_dir: str = "", headless: bool = True):
    global g_driver
    if not g_driver:
        chrome_options = ChromeOptions()
        if headless:
            chrome_options.add_argument("--headless")

        # Set user-agent to mimic a regular browser and disable webdriver flag to prevent detection of headless mode
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        prefs = {
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_settings.popups": 0,
            "download.extensions_to_open": "",
            "plugins.always_open_pdf_externally": True,
            "profile.default_content_setting_values.automatic_downloads": 1,
            "profile.content_settings.exceptions.automatic_downloads.*.setting": 1,
            "safebrowsing.disable_download_protection": True
        }
        if download_dir:
            prefs["download.default_directory"] = download_dir

        chrome_options.add_experimental_option("prefs", prefs)
        g_driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)


def list_xilinx_tools(timeout: float, **kwargs):
    if not g_driver:
        raise ValueError("Web driver is not initialized. Please initialize the web driver first.")

    g_driver.get("https://www.xilinx.com/support/download.html")
    available_categories = WebDriverWait(g_driver, timeout).until(
        EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class, \"xilinxTabs\")]/ul[contains(@class, \"nav\")]/descendant::a"))
    )
    return available_categories


def list_tool_tabs(tool_href: str, timeout: float, **kwargs):
    if not g_driver:
        raise ValueError("Web driver is not initialized. Please initialize the web driver first.")

    g_driver.execute_script("window.location.href = arguments[0];", tool_href)
    available_tabs = WebDriverWait(g_driver, timeout).until(
        EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class, \"tabs-left\")]/ul[contains(@class, \"nav\")]/descendant::a"))
    )
    return available_tabs


def list_tool_versions(tool_href: str, timeout: float, **kwargs):
    if not g_driver:
        raise ValueError("Web driver is not initialized. Please initialize the web driver first.")

    available_tabs = list_tool_tabs(tool_href, timeout)
    available_tabs_texts = []
    available_tabs_hrefs = []
    for tab in available_tabs:
        available_tabs_texts.append(tab.text.strip())
        available_tabs_hrefs.append(tab.get_attribute("href"))
    available_tabs = None

    versions = {}
    for text, href in zip(available_tabs_texts, available_tabs_hrefs):
        try:
            tool_version = SoftwareVersion(text)
            versions[text] = tool_version
        except ValueError:
            g_driver.execute_script("window.location.href = arguments[0];", href)
            downloadable_content = WebDriverWait(g_driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, \" xDownload\")]"))
            )
            collapsed_versions = downloadable_content.find_elements(
                By.XPATH,
                "descendant::button[contains(@data-toggle, \"collapse\")]"
            )
            if len(collapsed_versions) == 0:
                versions[text] = text.strip()
            else:
                versions[text] = []
                for cv in collapsed_versions:
                    versions[text].append(cv.text.strip())

    return versions


def get_download_progress(download_dir: str, filename: str, expected_size: int = 0):
    temp_file = sorted(Path(download_dir).glob(f"*.crdownload"), key=os.path.getmtime)
    if isinstance(temp_file, (list, tuple)) and len(temp_file) > 0:
        temp_file = temp_file[0]

    progress = 0
    if temp_file and os.path.exists(temp_file):
        progress = min(99.99, os.path.getsize(temp_file) / expected_size * 100)
    elif is_download_complete(download_dir, filename, expected_size):
        progress = 100

    return progress


def is_download_complete(download_dir: str, filename: str, expected_size: int = 0):
    download_file = sorted(Path(download_dir).glob(filename), key=os.path.getmtime)
    return (
        len(download_file) > 0
        and os.path.exists(download_file[0])
        and os.path.getsize(download_file[0]) / expected_size >= 1
    )


def get_xilinx_tool(target_tool, target_version, download_dir: str, timeout: float = 20, **kwargs):
    available_tools = list_xilinx_tools(timeout)
    if target_tool:
        choice = -1
        for idx, tool in enumerate(available_tools):
            if target_tool.lower() == format_tool_name(tool.text).lower():
                choice = idx
                break

        if choice == -1:
            raise ValueError(f"Specified tool \"{target_tool}\" is not found. Please check the available tools with --list-tools option.")
    else:
        info_message = "=" * 120
        for idx, tool in enumerate(available_tools):
            info_message += f"\n{idx + 1}. {format_tool_name(tool.text.strip())}"
        pager_print(info_message)

        choice_prompt = f"Choose the tool to list available versions [1-{len(available_tools)}]: "
        choice = str(input(choice_prompt))
        while not choice.isdigit() or int(choice) - 1 not in range(len(available_tools)):
            choice = str(input(choice_prompt))
        choice = int(choice) - 1

    available_tabs = list_tool_tabs(available_tools[choice].get_attribute("href"), timeout)
    if target_version:
        choice = -1
        for idx, elem in enumerate(available_tabs):
            if target_version.strip().lower() == elem.text.strip().lower():
                choice = idx
                break
            elif target_version.strip().lower().startswith(elem.text.strip().lower()):
                choice = idx
                target_version = target_version[len(elem.text):].strip()
                break

        if choice == -1:
            raise ValueError(f"Specified version \"{target_version}\" is not found. Please check the available versions with --list-tools option.")
    else:
        info_message = "=" * 120
        for idx, elem in enumerate(available_tabs):
            info_message += f"\n{idx + 1}. {elem.text.strip()}"
        pager_print(info_message)

        choice_prompt = f"Choose the version to download [1-{len(available_tabs)}]: "
        choice = str(input(choice_prompt))
        while not choice.isdigit() or int(choice) - 1 not in range(len(available_tabs)):
            choice = str(input(choice_prompt))
        choice = int(choice) - 1

    target_tab = available_tabs[choice]
    target_tab_url = target_tab.get_attribute("href")
    target_tab_text = target_tab.text.strip()

    g_driver.execute_script("window.location.href = arguments[0];", target_tab_url)
    downloadable_content = WebDriverWait(g_driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, "//div[contains(@class, \" xDownload\")]"))
    )

    download_divs = downloadable_content.find_elements(By.XPATH, "descendant::div[contains(@class, \"xilinxDCDownloadGroup\")]")
    collapsed_versions = downloadable_content.find_elements(By.XPATH, "descendant::button[contains(@data-toggle, \"collapse\")]")
    for collapsed in collapsed_versions:
        g_driver.execute_script("arguments[0].click();", collapsed)
        WebDriverWait(g_driver, timeout).until(lambda driver: collapsed.get_attribute("aria-expanded") == "true")
        if collapsed.text.lower().strip() == target_version.lower().strip():
            download_divs = collapsed.find_elements(By.XPATH, "parent::div/following-sibling::div/descendant::div[contains(@class, \"xilinxDCDownloadGroup\")]")
            break

    idx = 0
    download_hrefs = []
    if len(download_divs) > 0:
        info_message = "=" * 120
        for div in download_divs:
            try:
                header = div.find_element(By.XPATH, "descendant::div[@class=\"row\"]/div/h2").text
            except:
                header = ""
            if header:
                info_message += f"\n{header.strip()}"

            if kwargs.get("describe", False):
                try:
                    desc = div.find_element(By.XPATH, "descendant::div[@class=\"row\"]/descendant::div[@class=\"alert\"]").text
                except:
                    desc = ""
                if desc: # Avoid cluttering the output if there are too many versions
                    info_message += f"\n{desc.strip()}"

            info_message += "\n"
            hrefs = div.find_elements(By.XPATH, "descendant::li[@class=\"download-links\"]/descendant::a[not(@class)]")
            for href in hrefs:
                url = href.get_attribute("href")
                if "member/forms/download" in url:
                    idx += 1
                    title = href.get_attribute("data-original-title")
                    file_info = href.find_element(By.XPATH, "parent::p/child::span[contains(@class, \"subdued\")]").text
                    info_message += f"{idx}. {title} {file_info}\n"

                    download_hrefs.append((href, file_info.split("-")[-1][:-1].strip()))
            info_message += "=" * 120

        pager_print(info_message)
    else:
        raise ValueError(f"No files found for the specified tab \"{target_tab_text}\".")

    choice = str(input(
        f"Found {idx} downloadable files within tab \"{target_tab_text}\" ..." +\
        f"\nRead the descriptions above and choose the file to download [1-{idx}]: "
    ))
    while not choice.isdigit() or int(choice) - 1 not in range(idx):
        choice = str(input(
            f"Read the descriptions above and choose the file to download [1-{idx}]: "
        ))
    choice = int(choice) - 1

    current_url = g_driver.current_url
    target_href, target_size = download_hrefs[choice]
    size_in_bytes = size_str_to_nbytes(target_size)
    g_driver.execute_script("window.location.href = arguments[0];", target_href.get_attribute("href"))
    WebDriverWait(g_driver, timeout).until(EC.url_changes(current_url))

    if "login" in g_driver.current_url:
        current_url = g_driver.current_url
        print("Authentication is required ...")

        email_input = WebDriverWait(g_driver, timeout).until(EC.presence_of_element_located((By.XPATH, "//input[@name=\"identifier\"]")))
        pwd_input = g_driver.find_element(By.XPATH, "//input[@type=\"password\"]")
        submit_btn = g_driver.find_element(By.XPATH, "//input[@type=\"submit\"]")

        while True:
            print("=" * 120)
            email = str(input("Email: "))
            email_input.clear()
            email_input.send_keys(email)

            pwd = getpass("Password: ")
            pwd_input.clear()
            pwd_input.send_keys(pwd)

            g_driver.execute_script("arguments[0].click();", submit_btn)
            WebDriverWait(g_driver, timeout).until(
                lambda driver: driver.current_url != current_url \
                or EC.visibility_of_element_located((By.XPATH, "//div[contains(@class, \"error\") or contains(@class, \"Error\") or contains(@class, \"ERROR\")]"))(driver)
            )

            if current_url == g_driver.current_url:
                print("Failed to authenticate. Please check your credentials and try again.")
            else:
                print("Successfully authenticated!")
                break

    additional_inputs = {
        "First Name": (WebDriverWait(g_driver, timeout).until(EC.presence_of_element_located((By.XPATH, "//input[@name=\"First_Name\"]"))), False), # second element is a flag for optional fields
        "Last Name": (g_driver.find_element(By.XPATH, "//input[@name=\"Last_Name\"]"), False),
        "Company": (g_driver.find_element(By.XPATH, "//input[@name=\"Company\"]"), False),
        "Address 1": (g_driver.find_element(By.XPATH, "//input[@name=\"Address_1\"]"), False),
        "Address 2": (g_driver.find_element(By.XPATH, "//input[@name=\"Address_2\"]"), True),
        "Location": (Select(g_driver.find_element(By.XPATH, "//select[@name=\"Country\"]")), False),
        "State/Province": (g_driver.find_element(By.XPATH, "//input[@name=\"State\"]"), True), # There are special cases where it's required for some countries, updated depending on the location
        "City": (g_driver.find_element(By.XPATH, "//input[@name=\"City\"]"), False),
        "Postal Code": (g_driver.find_element(By.XPATH, "//input[@name=\"Zip_Code\"]"), True),
        "Phone": (g_driver.find_element(By.XPATH, "//input[@name=\"Phone\"]"), True),
        "Job Function": (Select(g_driver.find_element(By.XPATH, "//select[@name=\"Job_Function\"]")), False)
    }

    info_message = """
Additional information is required for the download ...
US Government Export Approval:
- U.S. export regulations require that your First Name, Last Name, Company Name and Shipping Address be verified before AMD can fulfill your download request. Please provide accurate and complete information.
- Addresses with Post Office Boxes and names/addresses with Non-Roman Characters with accents such as grave, tilde or colon are not supported by US export compliance systems.
    """.strip()
    pager_print(info_message)

    current_url = g_driver.current_url
    submit_btn = g_driver.find_element(By.XPATH, "//button[@type=\"SUBMIT\" or @type=\"submit\" or @type=\"Submit\"]")
    filename = g_driver.find_element(By.XPATH, "//input[@name=\"filename\" and @type=\"hidden\"]").get_attribute("value")
    filepath = os.path.join(download_dir, filename)
    start_time = 0
    while True:
        print("=" * 120)
        for key, elem in additional_inputs.items():
            in_request = ""
            elem, optional = elem
            if isinstance(elem, Select):
                options = elem.options[1:]
                previous_value = elem.first_selected_option.get_attribute("value")

                info_message = f"{key}:"
                for idx, option in enumerate(options):
                    info_message += f"\n\t{idx + 1}. {option.text}"
                pager_print(info_message)

                while True:
                    in_request = f"Choice [1-{len(options)}]"
                    if previous_value and previous_value.strip():
                        in_request += f" (optional, leave empty for autofilled value \"{previous_value}\"): " if optional\
                            else f" (leave empty for autofilled value \"{previous_value}\"): "
                    else:
                        in_request += f" (optional): " if optional else ": "
                    response = str(input(in_request))
                    if not response and previous_value and previous_value.strip():
                        break
                    if response.isdigit() and int(response) in range(1, len(options) + 1):
                        elem.select_by_index(int(response))
                        break

                if key == "Location":
                    state_selects = g_driver.find_elements(By.XPATH, "//select[@name=\"State\" and not(@disabled)]")
                    if len(state_selects) > 0:
                        state_select = Select(state_selects[0])
                        additional_inputs["State/Province"] = (state_select, False)
            else:
                previous_value = elem.get_attribute("value")
                if previous_value and previous_value.strip():
                    in_request = f"{key} (optional, leave empty for autofilled value \"{previous_value}\"): " if optional\
                        else f"{key} (leave empty for autofilled value \"{previous_value}\"): "
                else:
                    in_request = f"{key} (optional): " if optional else f"{key}: "
                while True:
                    response = str(input(in_request))
                    if not response and ((previous_value and previous_value.strip()) or optional):
                        break
                    if response:
                        elem.clear()
                        elem.send_keys(response)
                        break                 

        g_driver.execute_script("arguments[0].click();", submit_btn)
        WebDriverWait(g_driver, timeout).until(
            lambda driver: get_download_progress(download_dir, filename, size_in_bytes) > 0 \
            or WebDriverWait.until(EC.visibility_of_element_located((By.XPATH, "//div[contains(@id, \"Error\") or contains(@id, \"error\") or contains(@id, \"ERROR\")]"))(driver))
        )

        start_time = time.time()
        if get_download_progress(download_dir, filename, size_in_bytes) > 0:
            break
        else:
            print("Failed to download the binary. Please check your information and try again.")

    print("=" * 120)
    print(f"{filename} ({target_size})")
    while True:
        time.sleep(1)
        progress = get_download_progress(download_dir, filename, size_in_bytes)

        elapsed_time = time.time() - start_time
        if progress > 0:
            remaining_time = (100 - progress) * elapsed_time / progress
        else:
            remaining_time = 0
        elapsed_str = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        remaining_str = time.strftime("%H:%M:%S", time.gmtime(remaining_time))

        print(f"\rDownload progress: {progress:.2f}% | Elapsed: {elapsed_str} | Remaining: {remaining_str}", end="")
        if progress >= 100:
            break

    print(f"\nFile saved to {filepath}")
    input("Press Enter to exit ...")


def main(args):
    get_chrome_driver(args.output, headless=True)

    if args.list_tools:
        tools = list_xilinx_tools(args.timeout)
        tools_texts: list[str] = []
        tools_hrefs: list[str] = []
        for tool in tools:
            tools_texts.append(format_tool_name(tool.text.strip()))
            tools_hrefs.append(tool.get_attribute("href"))
        tools = None # will turn stale once we navigate to a different page, clear it and use copied info

        versions = {
            text: list_tool_versions(href, args.timeout) for text, href in zip(tools_texts, tools_hrefs)
        }

        info_message = "=" * 120
        info_message += "\nAvailable tools and versions:"
        for idx, text in enumerate(tools_texts):
            prefix = f"{idx + 1}. {text}:"
            tool_versions = versions[text]
            versions_texts = ""
            for k, v in tool_versions.items():
                if isinstance(v, list):
                    for version in v:
                        full_version = f"{k} {version}"
                        if versions_texts:
                            versions_texts += ","
                        versions_texts += f" \"{full_version}\""
                else:
                    version = v if isinstance(v, str) else str(v)
                    if versions_texts:
                        versions_texts += ","
                    versions_texts += f" \"{version}\""
            info_message += f"\n{prefix}{versions_texts}"
        pager_print(info_message)
    else:
        get_xilinx_tool(args.tool, args.version, args.output, timeout=args.timeout, describe=args.describe)

    global g_driver
    if g_driver:
        g_driver.quit()
        g_driver = None


if __name__ == "__main__":
    home_dir = os.path.expanduser("~")

    parser = argparse.ArgumentParser(description="Automated download script for Xilinx tools.")
    parser.add_argument("-t", "--tool", default="", help="Specify the tool to download (e.g., vivado, vitis, petalinux, etc.)")
    parser.add_argument("-v", "--version", default="", help="Specify the version of the tool (e.g., 2024.1)")
    parser.add_argument("-o", "--output", default=home_dir, help=f"Specify the download output directory (default: {home_dir})")
    parser.add_argument("-ti", "--timeout", default=20, type=float, help="Specify the timeout in seconds for each web request (default: 20)")
    parser.add_argument("-lt", "--list-tools", action="store_true", help="List all available tools and versions")
    parser.add_argument("--describe", action="store_true", help="Print downloadable files descriptions")

    args = parser.parse_args()
    main(args)
