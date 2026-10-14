<img width=50 src="assets/Icon.png">

# OSWarp

[![Python 3.7+](https://img.shields.io/badge/Python-3.7+-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![C#](https://img.shields.io/badge/C%23-.NET%20Framework%204.5+-239120?logo=csharp&logoColor=white)](https://learn.microsoft.com/dotnet/csharp/) [![MIT License](https://img.shields.io/badge/License-MIT-blue)](LICENSE) ![Partially AI Coded](https://img.shields.io/badge/Partially%20AI%20Coded-Human%20Reviewed-A855F7)

OSWarp is a shortcut for rebooting between installed operating systems. It is especially useful if you dual-boot Windows and Linux. It can also help when the Linux install doesn't recognize Windows and add it to the GRUB menu.

Choose a boot method at first run. You can choose BootNext if you only want to change the boot once, or BootOrder to change it permanently. You can also change it later.

## AI usage

This program is made partially using AI with careful practices such as unit tests. It also does the job through external tools as much as possible to prevent anything from going wrong. 

The code has been reviewed by a human and tested on both VM and real hardware. Don't use it if you don't trust it.

## Screenshots

| Linux (KDE) | Windows |
| --- | --- |
| <img width=200 src="assets/linux1.png"> | <img width=200 src="assets/windows1.png"> |
| <img width=200 src="assets/linux2.png"> | <img width=200 src="assets/windows2.png"> |

## Install

### Linux

Download the Python release.

```sh
chmod a+x install.sh
./install.sh
```

It will then appear in your applications menu. You can also use the command "oswarp".

To try it without installing:

```sh
chmod a+x run.sh
./run.sh
```

### Windows

Download the Windows release and put the single "OSWarp.exe" file wherever you like.

## How it works

This tool changes the UEFI boot order or adds a one-time config when you click on "Reboot". On Linux, it uses efibootmgr. On Windows, it uses bcdedit. It can recognize the right boot entry and select it for you if you are dual-booting Windows and Linux. You can also choose one manually.

Some motherboard firmware might not support changing the boot order from software. For example, some MSI motherboards have a feature called "BBS Priority" which sometimes overwrites the changes.

The alert UI uses kdialog, zenity, or yad, depending on your desktop environment.

## Build

### Linux

There is no need to build.

### Windows

Make sure you have Visual Studio and run `build.bat`.

## License

OSWarp is released under the MIT License. You can use, copy, modify, and distribute it, including for commercial use. Copies and substantial portions must keep the copyright notice and this license. The software is provided as is, without warranty. The full text is in [LICENSE](LICENSE).
