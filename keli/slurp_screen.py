from keli.slurpthing import SlurpThing
import uuid
import subprocess

# many of these classes use subprocess calls to gnome-screenshot
# since this was initially created on fedora running wayland
# however, a more cross-window manager (and X/wayland) tool
# would be better

class SlurpScreenshot(SlurpThing):
    def __init__(self, **kwargs):
        super(SlurpScreenshot, self).__init__(**kwargs)
        self.slurp_method = "screenshot"
        self.virtual_device_pattern = "virtualdev:screenshot:*"

    def slurpd(self, device):
        screenshot_file = "/tmp/{}".format(str(uuid.uuid4()))
        subprocess.call(["gnome-screenshot", "-f", screenshot_file])
        return self.file_bytes(screenshot_file)

class SlurpScreenshotRegion(SlurpThing):
    def __init__(self, **kwargs):
        super(SlurpScreenshotRegion, self).__init__(**kwargs)
        self.slurp_method = "screenshot_region"
        self.virtual_device_pattern = "virtualdev:screenshot-region:*"

    def slurpd(self, device):
        screenshot_file = "/tmp/{}".format(str(uuid.uuid4()))
        subprocess.call(["gnome-screenshot", "-a", "-f", screenshot_file])
        return self.file_bytes(screenshot_file)

class SlurpScreenshotWindow(SlurpThing):
    def __init__(self, **kwargs):
        super(SlurpScreenshotWindow, self).__init__(**kwargs)
        self.slurp_method = "screenshot_window"
        self.virtual_device_pattern = "virtualdev:screenshot-window:*"

    def slurpd(self, device):
        screenshot_file = "/tmp/{}".format(str(uuid.uuid4()))
        # delay for 5 seconds to allow window to be selected
        subprocess.call(["gnome-screenshot", "-w", "-d", "5", "-f", screenshot_file])
        return self.file_bytes(screenshot_file)

class SlurpScreenshotAnimated(SlurpThing):
    def __init__(self, **kwargs):
        super(SlurpScreenshotAnimated, self).__init__(**kwargs)
        # ScreenCast? ScreenCastAnimated?
        self.slurp_method = "screenshot_animated"
        self.virtual_device_pattern = "virtualdev:screenshot-animated:*"

    def slurpd(self, device):
        # uses peek and requires user to save
        # file as /tmp/peek.gif
        # since there is only a file save dialog and no --output flag
        screenshot_file = "/tmp/peek.gif"
        subprocess.call(["peek"])
        return self.file_bytes(screenshot_file)
