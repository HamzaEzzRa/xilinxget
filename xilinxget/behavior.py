import math
import random
import time
from typing import TYPE_CHECKING, Optional

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

if TYPE_CHECKING:
    from selenium.webdriver.remote.webelement import WebElement
    from selenium.webdriver.support.ui import Select
    from undetected_chromedriver import Chrome


def dismiss_cookie_notice(driver: "Chrome") -> bool:
    # OneTrust and common cookie consent patterns
    selectors = [
        "//button[@id='onetrust-accept-btn-handler']",
        "//button[contains(@class,'accept') and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept all')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'got it')]",
    ]
    WebDriverWait(driver, 3).until(lambda d: any(d.find_elements(By.XPATH, xpath) for xpath in selectors))
    for xpath in selectors:
        buttons = driver.find_elements(By.XPATH, xpath)
        for btn in buttons:
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(random.uniform(0.3, 0.6))
                return True
    return False


def scroll_to_element(driver: "Chrome", element: "WebElement"):
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(random.uniform(0.2, 0.4))  # Brief pause after scrolling


def human_click(driver: "Chrome", element: "WebElement"):
    scroll_to_element(driver, element)
    ActionChains(driver).move_to_element(element).pause(random.uniform(0.1, 0.3)).perform()
    time.sleep(random.uniform(0.05, 0.15))
    element.click()


def human_select(
    driver: "Chrome",
    select_element: "Select",
    *,
    index: Optional[int] = None,
    value: Optional[str] = None
):
    if index is None and value is None:
        raise ValueError("Either index or value must be provided.")

    scroll_to_element(driver, select_element._el)
    # Click to open the dropdown before selecting
    ActionChains(driver).move_to_element(select_element._el).pause(random.uniform(0.08, 0.15)).click().perform()
    time.sleep(random.uniform(0.15, 0.3))
    if index is not None:
        select_element.select_by_index(index)
    elif value is not None:
        select_element.select_by_value(value)


def human_mouse_wander(driver: "Chrome", duration: float = 3.0):
    """
    Move the mouse along random bezier curves for `duration` seconds.
    This generates the movement entropy that Akamai's sensor script requires
    before it will accept a form submission as human.
    """
    def _bezier(t, p0, p1, p2, p3):
        return (
            (1-t)**3*p0[0] + 3*(1-t)**2*t*p1[0] + 3*(1-t)*t**2*p2[0] + t**3*p3[0],
            (1-t)**3*p0[1] + 3*(1-t)**2*t*p1[1] + 3*(1-t)*t**2*p2[1] + t**3*p3[1],
        )

    vw, vh = driver.execute_script("return [window.innerWidth, window.innerHeight];")

    # move_by_offset is relative to the unknown current pointer position.
    # Anchor to a known visible element first via move_to_element, then read
    # its viewport-relative center so we can track absolute coords from there.
    anchor = next(
        (e for xpath in [
            "//input[not(@type='hidden') and not(@disabled)]",
            "//select[not(@disabled)]",
            "//button",
            "//a",
        ] for e in driver.find_elements(By.XPATH, xpath) if e.is_displayed()),
        None
    )
    if anchor is None:
        return

    rect = driver.execute_script("return arguments[0].getBoundingClientRect();", anchor)
    x = max(1, min(vw - 1, int(rect["left"] + rect["width"] / 2)))
    y = max(1, min(vh - 1, int(rect["top"] + rect["height"] / 2)))
    ActionChains(driver).move_to_element(anchor).perform()

    end_time = time.time() + duration
    while time.time() < end_time:
        # Pick a random destination within the viewport
        tx = random.randint(50, vw - 50)
        ty = random.randint(50, vh - 50)

        # Random bezier control points for a natural curve
        cp1 = (x + (tx - x) * random.uniform(0.2, 0.5) + random.randint(-80, 80),
               y + (ty - y) * random.uniform(0.2, 0.5) + random.randint(-80, 80))
        cp2 = (x + (tx - x) * random.uniform(0.5, 0.8) + random.randint(-80, 80),
               y + (ty - y) * random.uniform(0.5, 0.8) + random.randint(-80, 80))

        steps = random.randint(15, 30)
        actions = ActionChains(driver)
        px, py = x, y
        for i in range(1, steps + 1):
            t = i / steps
            nx, ny = _bezier(t, (x, y), cp1, cp2, (tx, ty))
            # Clamp to viewport so we never go out of bounds
            nx = max(1, min(vw - 1, int(nx)))
            ny = max(1, min(vh - 1, int(ny)))
            # Ease in-out speed: slow at ends, fast in middle
            speed = 0.5 - 0.5 * math.cos(math.pi * t)
            dx, dy = nx - px, ny - py
            if dx or dy:
                actions.move_by_offset(dx, dy).pause(random.uniform(0.005, 0.02) / (speed + 0.1))
            px, py = nx, ny
        actions.perform()

        x, y = int(tx), int(ty)
        time.sleep(random.uniform(0.1, 0.4))  # Pause between curves (simulates reading)


def human_type(driver: "Chrome", element: "WebElement", text: str):
    scroll_to_element(driver, element)
    # Click the field first, then select-all + delete to clear naturally
    ActionChains(driver).move_to_element(element).click().perform()
    time.sleep(random.uniform(0.1, 0.2))
    element.send_keys(Keys.CONTROL + "a")
    time.sleep(random.uniform(0.05, 0.1))
    element.send_keys(Keys.DELETE)
    time.sleep(random.uniform(0.1, 0.2))
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.18))
