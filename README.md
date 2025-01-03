# urcontrol

Python-based GUI, open-source library and command-line tool to control the Steinberg UR44C Mixer and DSP.

Probably will work with other models like UR22C, UR24C, and UR816C with minor changes; however, I can't test because I don't have such equipment.

The goal of this project is to replace dspMixFx, as it is not available for Linux and also doesn't work under Wine.

Note: The GUI is in a very early state so far. Help in completing the GUI is very appreciated.

## Reverse Engineering

The UR44C has two MIDI ports available via USB: the first one is physical MIDI interface, and the second one is internally connected to the Yamaha Mixer with DSP for control purposes.
When no drivers are installed, the deviceworks in Class Compliant mode, and both MIDI ports are available in the system.
But after installing official drivers, the second port becomes hidden, and only the proprietary dspMixFx application can access it.

The Mixer is controlled by SYSEX messages with Yamaha manufacturer identifier and common Yamaha SYSEX message structure.

Currently, only a few protocol messages are recognized. If you want to recognize more, you may be interested in preparing the following setup:
- Use a Linux host
- Install Windows 10 in VirtualBox, install Steinberg drivers and tools into it.
- Connect your sound card and forward it into Windows
- Enable usbmon kernel module (`sudo modprobe usbmon`)
- Copy `mixer-control-protocol.lua` into the Wireshark Global Lua Plugins folder (you can find the path in Help > About Wireshark > Folders)
- Run Wireshark with root or USB access permission
- Open the usbmon* port (try several to find which one has the connected device)


## TODO / Plans
- Complete GUI (aka dspMixFx replacement)
- Recognize Sysex messages for storing/loading presets and bulk configuring of the device
- Fully recognize Sysex messages for peak meters (some work is done, but additional sections like StreamingMix, Music, Voice are not recognized yet)
- Recognize how the 3 virtual outputs (DAW/Music/Voice) are realized and try to implement it in Linux


## Disclaimer
This software is developed for research purposes only.
By using it, you do so at your own risk.
The authors have no responsibility for any consequences, including potential device brick, violating manufacturer licenses, lose device warranty etc.
