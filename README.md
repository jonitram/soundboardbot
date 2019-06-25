**For use:**  
  
1. Clone git repository through this command (requires git):  
  
    > $ git clone https://github.com/jonitram/soundboardbot.git  
  
    If you do not have git installed, it can be installed via these commands depending on your operating system:  
  
    Mac (git):  
  
    > $ brew install git  
  
    Linux (git):  
  
    $ sudo apt-get update  
    $ sudo apt-get install git-core  
  
2. You will need your own discord and youtube api tokens to use this bot, so register the bot as a discord developer and acquire a youtube api token at these locations:  
  
    Discord Developer: https://discordapp.com/developers  
    Google Developer: https://console.developers.google.com  
  
3. Additionally, the bot requires 'ffmpeg' for audio manipulation. This can be installed via these commands depending on your operating system:  
  
    Mac (ffmpeg):  
  
    $ brew install ffmpeg  
  
    Linux (ffmpeg):  
  
    $ sudo apt-get update  
    $ sudo apt-get install ffmpeg  
  
    Linux (libav-tools, ffmpeg may require libav-tools):  
  
    $ sudo apt-get install libav-tools  
  
4. The bot also requires 'python3.7' and 'pip3' for installation and running the bot. These can be installed via these commands depending on your operating system:  
  
    Mac (python3.7 and pip3):  
  
    $ brew install python3  
  
    Linux (python3.7):  
  
    $ sudo apt update  
    $ sudo apt install build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev wget  
    $ wget https://www.python.org/ftp/python/3.7.3/Python-3.7.3.tar.xz  
    $ tar -xf Python-3.7.3.tar.xz  
    $ cd Python-3.7.3  
    $ ./configure --enable-optimizations  
    $ make  
    $ sudo make altinstall  
  
    Linux (pip3):  
  
    $ sudo apt-get update  
    $ sudo apt-get -y install python3-pip  
  
    Linux (pip3, alternative method):  
  
    $ curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python3  
  
5. To set the bot up, run this command (requires python3.7 and pip3):  
  
    $ sh setup.sh  
  
6. To start the bot, run this command (requires python 3.7):  
  
    $ python3.7 soundboardbot.py  
  
7. Finally, to issue commands to the bot, use the prefix ".sbb" followed by a space and the command.  
    ".sbb help" will explain each of the bot's commands in depth along with how to use them.
