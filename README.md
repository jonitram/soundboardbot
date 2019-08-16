# Soundboardbot 

## Purpose: 

The purpose of this bot is to allow users in a discord server to clip audio from youtube videos and create their own commands. The bot will cache downloaded audio until a command is saved for near instantaneous testing and retrimming of the command currently being created. The bot can only perform one audio command at a time, but the entire bot functions concurrently, so the currently playing audio command can be stopped and audio commands being created and processed in the background can be cancelled at any time.

## Setup: 

1. Clone git repository through this command: 
 
    `$ git clone https://github.com/jonitram/soundboardbot.git` 
 
2. You will need your own discord and youtube api tokens to host this bot, so register the bot as a discord developer and acquire a youtube api token at these locations: 
 
    Discord Developer: https://discordapp.com/developers  
    Google Developer: https://console.developers.google.com 
 
3. To install all of the bot's dependencies, run this command and follow the prompts for your api tokens: 
 
    `$ sh setup.sh` 
 
## Usage: 

1. To start the bot, run this command: 
 
    `$ python3.7 soundboardbot.py` 
 
2. To issue commands to the bot in discord, use the message prefix "sbb" followed by a space and the command. For example, this message will display usage of each of the bot's commands: 
 
    `sbb help` 

