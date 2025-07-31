import argparse
import os
import re
import time
from getpass import getpass
from glob import glob
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


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
    return len(download_file) > 0 and os.path.exists(download_file[0]) and os.path.getsize(download_file[0]) / expected_size >= 1

def get_vivado_bin(target_version: str, download_dir: str, timeout: float = 20):
    target_version = SoftwareVersion(target_version)

    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless")
    # Set user-agent to mimic a regular browser and disable webdriver flag to prevent detection of headless mode
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    prefs = {
        "download.default_directory": download_dir,
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
    chrome_options.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)

    driver.get("https://www.xilinx.com/support/download/index.html/content/xilinx/en/downloadNav/vivado-design-tools.html")
    versions_list = WebDriverWait(driver, timeout).until(
        EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class, \"tabs-left\")]/ul[contains(@class, \"nav\")]/descendant::a"))
    )

    archive_href = ""
    versions_dict = {}
    highest_version = None
    for idx, elem in enumerate(versions_list):
        match = re.match(r"(\d+)\.(\d+)", elem.text)
        if match:
            version = SoftwareVersion(elem.text)
            versions_dict[version] = elem
            if not highest_version or version > highest_version:
                highest_version = version
        elif "archive" in elem.text.lower() and not archive_href: # Consider first archive tab
            archive_href = elem

    if target_version > highest_version:
        raise ValueError(
            f"Version {target_version} is not available on the Xilinx downloads page." +\
            f"\nHighest version available is {highest_version}."
        )

    target_href = versions_dict.get(target_version, archive_href)
    target_url = target_href.get_attribute("href")

    driver.execute_script("window.location.href = arguments[0];", target_href.get_attribute("href"))
    WebDriverWait(driver, timeout).until(lambda driver: driver.current_url == target_url)

    idx = 0
    download_divs = []
    download_hrefs = []
    if target_href == archive_href:
        collapsed_versions = driver.find_elements(By.XPATH, "//button[contains(@data-toggle, \"collapse\")]")
        for collapsed in collapsed_versions:
            if collapsed.text.strip() == str(target_version):
                driver.execute_script("arguments[0].click();", collapsed)
                WebDriverWait(driver, timeout).until(lambda driver: collapsed.get_attribute("aria-expanded") == "true")
                download_divs = driver.find_elements(By.XPATH, "//div[contains(@id, \"collapse\") and @aria-expanded=\"true\"]/descendant::div[contains(@class, \"xilinxDCDownloadGroup\")]")
                break
    else:
        download_divs = driver.find_elements(By.XPATH, "//div[contains(@class, \"xilinxDCDownloadGroup\")]")
    if len(download_divs) > 0:
        print("=" * 120)
        for div in download_divs:
            try:
                header = div.find_element(By.XPATH, "descendant::div[@class=\"row\"]/div/h2").text
            except:
                header = ""
            if header:
                print(header.strip())

            try:
                desc = div.find_element(By.XPATH, "descendant::div[@class=\"row\"]/descendant::div[@class=\"alert\"]").text
            except:
                desc = ""
            if desc:
                print(desc.strip())

            hrefs = div.find_elements(By.XPATH, "descendant::li[@class=\"download-links\"]/descendant::a[not(@class)]")
            for href in hrefs:
                url = href.get_attribute("href")
                if str(target_version) in url or "member/forms/download" in url:
                    idx += 1
                    title = href.get_attribute("data-original-title")
                    file_info = href.find_element(By.XPATH, "parent::p/child::span[contains(@class, \"subdued\")]").text
                    print(f"({idx}): {title} {file_info}")

                    download_hrefs.append((href, file_info.split("-")[-1][:-1].strip()))

            print("=" * 120)
    else:
        raise ValueError(f"No files found for the specified version {target_version}.")

    choice = str(input(
        f"Found {idx} files associated with version {target_version} ..." +\
        f"\nRead the descriptions above and choose the file to download [1-{idx}]: "
    ))
    while not choice.isdigit() or int(choice) - 1 not in range(idx):
        choice = str(input(
            f"Read the descriptions above and choose the file to download [1-{idx}]: "
        ))
    choice = int(choice) - 1

    current_url = driver.current_url
    target_href, target_size = download_hrefs[choice]
    size_in_bytes = size_str_to_nbytes(target_size)
    driver.execute_script("window.location.href = arguments[0];", target_href.get_attribute("href"))
    WebDriverWait(driver, timeout).until(EC.url_changes(current_url))

    if "login" in driver.current_url:
        current_url = driver.current_url
        print("Authentication is required ...")

        email_input = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, "//input[@name=\"identifier\"]")))
        pwd_input = driver.find_element(By.XPATH, "//input[@type=\"password\"]")
        submit_btn = driver.find_element(By.XPATH, "//input[@type=\"submit\"]")

        while True:
            print("=" * 120)
            email = str(input("Email: "))
            email_input.clear()
            email_input.send_keys(email)

            pwd = getpass("Password: ")
            pwd_input.clear()
            pwd_input.send_keys(pwd)

            driver.execute_script("arguments[0].click();", submit_btn)
            WebDriverWait(driver, timeout).until(
                lambda driver: driver.current_url != current_url \
                or EC.visibility_of_element_located((By.XPATH, "//div[contains(@class, \"error\") or contains(@class, \"Error\") or contains(@class, \"ERROR\")]"))(driver)
            )

            if current_url == driver.current_url:
                print("Failed to authenticate. Please check your credentials and try again.")
            else:
                print("Successfully authenticated!")
                break

    additional_inputs = {
        "First Name": (WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, "//input[@name=\"First_Name\"]"))), False), # second element is a flag for optional fields
        "Last Name": (driver.find_element(By.XPATH, "//input[@name=\"Last_Name\"]"), False),
        "Company": (driver.find_element(By.XPATH, "//input[@name=\"Company\"]"), False),
        "Address 1": (driver.find_element(By.XPATH, "//input[@name=\"Address_1\"]"), False),
        "Address 2": (driver.find_element(By.XPATH, "//input[@name=\"Address_2\"]"), True),
        "Location": (Select(driver.find_element(By.XPATH, "//select[@name=\"Country\"]")), False),
        "State/Province": (driver.find_element(By.XPATH, "//input[@name=\"State\"]"), True), # There are special cases where it's required for some countries, updated depending on the location
        "City": (driver.find_element(By.XPATH, "//input[@name=\"City\"]"), False),
        "Postal Code": (driver.find_element(By.XPATH, "//input[@name=\"Zip_Code\"]"), True),
        "Phone": (driver.find_element(By.XPATH, "//input[@name=\"Phone\"]"), True),
        "Job Function": (Select(driver.find_element(By.XPATH, "//select[@name=\"Job_Function\"]")), False)
    }

    print("Additional information is required for the download ...")
    print("U.S. Government Export Approval:")
    print(
        "- U.S. export regulations require that your First Name, Last Name, Company Name and Shipping Address be verified before AMD can fulfill your download request. " +\
        "Please provide accurate and complete information."
    )
    print("- Addresses with Post Office Boxes and names/addresses with Non-Roman Characters with accents such as grave, tilde or colon are not supported by US export compliance systems.")

    current_url = driver.current_url
    submit_btn = driver.find_element(By.XPATH, "//button[@type=\"SUBMIT\" or @type=\"submit\" or @type=\"Submit\"]")
    filename = driver.find_element(By.XPATH, "//input[@name=\"filename\" and @type=\"hidden\"]").get_attribute("value")
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
                print(f"{key}:")
                for idx, option in enumerate(options):
                    print(f"\t({idx + 1}): {option.text}")
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
                    state_selects = driver.find_elements(By.XPATH, "//select[@name=\"State\" and not(@disabled)]")
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

        driver.execute_script("arguments[0].click();", submit_btn)
        WebDriverWait(driver, timeout).until(
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

    driver.quit()


if __name__ == "__main__":
    home_dir = os.path.expanduser("~")

    parser = argparse.ArgumentParser(description="Automated download script for Vivado binaries.")
    parser.add_argument('-v', '--version', required=True, help="Specify the Vivado version (e.g., 2024.1)")
    parser.add_argument('-o', '--output', default=home_dir, help=f"Specify the download output directory (default: {home_dir})")
    parser.add_argument('-t', '--timeout', default=20, type=float, help="Specify the timeout in seconds for each web request (default: 20)")

    args = parser.parse_args()

    get_vivado_bin(args.version, args.output, timeout=args.timeout)
