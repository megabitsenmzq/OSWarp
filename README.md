<img width=50 src="assets/Icon.png">

# OSWarp

[![Python 3](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![C#](https://img.shields.io/badge/C%23-.NET%20Framework-239120?logo=csharp&logoColor=white)](https://learn.microsoft.com/dotnet/csharp/) [![MIT License](https://img.shields.io/badge/License-MIT-blue)](LICENSE) ![Vibe Coded](https://img.shields.io/badge/Partially%20AI%20Coded-Human%20Reviewed-A855F7)

OSWarp is a shortcut for rebooting between installed operating systems. It is especially useful if you dual-boot Windows and Linux.

## Screenshots

| Linux (KDE) | Windows |
| --- | --- |
| <img width=200 src="assets/linux1.png"> | <img width=200 src="assets/windows1.png"> |
| <img width=200 src="assets/linux2.png"> | <img width=200 src="assets/windows2.png"> |

## Install

### Linux / BSD

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

This tool changes the UEFI boot order when you click on "Reboot". On Linux, it uses efibootmgr to change the boot order. On Windows, it uses bcdedit. It can recognize the right boot entry and select it for you if you are dual-booting Windows and Linux. You can also choose one manually.

The alert UI uses kdialog, zenity, or yad, depending on your desktop environment.

## Build

### Linux

There is no need to build.

### Windows

Make sure you have Visual Studio and run `build.bat`.

## License

OSWarp is released under the MIT License. You can use, copy, modify, and distribute it, including for commercial use. Copies and substantial portions must keep the copyright notice and this license. The software is provided as is, without warranty. The full text is in [LICENSE](LICENSE).
