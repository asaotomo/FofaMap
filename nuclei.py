import platform


class Scan:
    def __init__(self):
        self.system = platform.system()
        self.machine = platform.machine()
        if "Darwin" in self.system and "arm64" in self.machine:
            self.path = "./nuclei/macos/nuclei_arm"
        elif "Darwin" in self.system and "amd64" in self.machine:
            self.path = "./nuclei/macos/nuclei_amd"
        elif "Linux" in self.system and "armv6" in self.machine:
            self.path = "./nuclei/linux/nuclei_armv6"
        elif "Linux" in self.system and "arm" in self.machine:
            self.path = "./nuclei/linux/nuclei_arm"
        elif "Linux" in self.system and "386" in self.machine:
            self.path = "./nuclei/linux/nuclei_386"
        elif "Linux" in self.system and "x86_64" in self.machine:
            self.path = "./nuclei/linux/nuclei_amd"
        elif "Windows" in self.system and "x86_64" in self.machine:
            self.path = "nuclei\\windows\\nuclei_386.exe"
        elif "Windows" in self.system and "AMD64" in self.machine:
            self.path = "nuclei\\windows\\nuclei_amd.exe"
        else:
            self.path = None

    def single_target(self, target, filename="scan_result.txt"):
        if "windows" in self.path:
            self.cmd = "{} -u {} -o {} -nc".format(self.path, target, filename)
        else:
            self.cmd = "{} -u {} -o {}".format(self.path, target, filename)
        return self.cmd

    def multi_target(self, target, filename="scan_result.txt"):
        if "windows" in self.path:
            self.cmd = "{} -l {} -o {} -nc".format(self.path, target, filename)
        else:
            self.cmd = "{} -l {} -o {}".format(self.path, target, filename)
        return self.cmd

    def single_multi_target(self, target, key, value, filename="scan_result.txt"):
        if "windows" in self.path:
            self.cmd = "{} -{} {} -u {} -o {} -nc".format(self.path, key, value, target, filename)
        else:
            self.cmd = "{} -{} {} -u {} -o {}".format(self.path, key, value, target, filename)
        return self.cmd

    def keyword_multi_target(self, target, key, value, filename="scan_result.txt"):
        if "windows" in self.path:
            self.cmd = "{} -{} {} -l {} -o {} -nc".format(self.path, key, value, target, filename)
        else:
            self.cmd = "{} -{} {} -l {} -o {}".format(self.path, key, value, target, filename)
        return self.cmd

    def customize_cmd(self, target, customize_cmd, filename="scan_result.txt"):
        if "windows" in self.path:
            self.cmd = "{} {} -l {} -o {} -nc".format(self.path, customize_cmd, target, filename)
        else:
            self.cmd = "{} {} -l {} -o {}".format(self.path, customize_cmd, target, filename)
        return self.cmd

    def update(self):
        if "windows" in self.path:
            self.cmd = "{} -update -nc".format(self.path)
        else:
            self.cmd = "{} -update".format(self.path)
        return self.cmd
