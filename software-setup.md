## ⚙ configuring the Raspberry Pi for project

> [!NOTE]
>
> The following set of instructions assumes you are running Raspberry Pi OS Lite. 

We will need to get pip. Doesn't seem to get packaged by default.

```shell
sudo apt install python3-pip
```

and we need to enable I2C and SPI with the following commands

```shell
sudo raspi-config nonint do_i2c 0
```

```shell
sudo raspi-config nonint do_spi 0
```

We also need to increase the SPI buffer size, as the default is only 4096 bytes. To do so, we edit `cmdline.txt` by running

```shell
sudo nano /boot/cmdline.txt
```

and we add the following entry to increase the buffer size to 65536  bytes:

```
spidev.bufsiz=65536  
```

> [!IMPORTANT]
>
> Note that after setting these new values you will need to restart the raspberry pi for the changes to go into effect.

#### 🐍 Python packages

Finally, we will need to install some python packages:

```shell
sudo apt install python3-smbus
```

```shell
sudo apt install python3-spidev
```

```shell
sudo apt install python3-numpy
```

```shell
sudo apt install python3-pillow
```

> [!NOTE]
>
> For some reason Pi OS Lite doesn't love installing via pip, so the commands above are used. I am sure you could install it via pip with minimal effort.