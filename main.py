# Label_Tool 项目主入口
# Author: Dr.Ash
# Maintainer: Dr.Ash
# Repository: https://github.com/Drash-2077/Label_Tool
# License: MIT

import sys
from PyQt5.QtWidgets import QApplication
from Gui import App 

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec_())