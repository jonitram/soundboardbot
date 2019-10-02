#!/usr/bin/env python3
import asyncio
import discord
import pafy
from pydub import AudioSegment
import multiprocessing
import subprocess
import random
import os
import sys

# TODO:
# maybe change finished from a list to a value/queue

# multiprocessing manager for sharing information across child processes
mpmanager = multiprocessing.Manager()

# api tokens
discord_token=None
youtube_token=None

# the text file that the tokens are stored in
tokensfile = "tokens.txt"

# the message prefix required to call the bot in discord
command_prefix = 'sbb'
# the filename prefix for audio files related to the bot
file_prefix = 'sbb_'
# the filetype for audio files downloaded for commands
file_suffix = '.mp3'
# the video format for videos downloaded from youtube
video_formatting = 'm4a'
# audio commands
audio_commands = []
# other commands sorted in alphabetical order
other_commands = ['cancel','cleanup','clear','create','creating','help','list','stop','random','remove','rename','restart','retrim','save','upload']
command_explanations = [' \"cancel\" : Cancels the audio command currently being created.',
                        ' \"cleanup\" : Toggles automatically deleting commands issued to the bot. When this is disabled, the bot will also send the amount of messages deleted by \"clear\".',
                        ' \"clear\" : Deletes commands issued to the bot and messages sent by the bot (up to 500 messages back).',
                        ' \"create <YouTubeURL> <CommandName> <StartTime(Min:Sec)> <Duration(Sec)>\" : Creates an audio command called <CommandName> from <YouTubeURL> starting at <StartTime> through <Duration>.\n'\
                            'Each parameter of the \"create\" command must be separated by a space. Only one audio command can be created at a time.'\
                            ' You will get a chance to test your command and retrim it if you would like to before saving it.',
                        ' \"creating\" : Displays the audio command currently being created.',
                        ' \"help\" : Sends the help message.',
                        ' \"list\" : Lists all available audio commands.',
                        ' \"stop\" : Stops a currently playing audio command.',
                        ' \"random\" : Randomly selects an audio command and executes it (will only work in an audio channel).',
                        ' \"remove <CommandName>\" : Removes the <CommandName> audio command.',
                        ' \"rename <CurrentCommandName> <NewCommandName>\" : Renames the currently existing <CurrentCommandName> to <NewCommandName>.',
                        ' \"restart\" : Stops all audio commands, cancels the command currently being created, restarts and updates the bot.',
                        ' \"retrim <StartTime(Min:Sec)> <Duration(Sec)>\" : Retrims the audio command currently being created before it is saved (will only work after downloading is complete).',
                        ' \"save\" : Completes the \"create\" command process and saves your command.',
                        ' \"upload <CommandName>\" : Creates a command called <CommandName> using the uploaded attachment. Exactly one attachment must be used, the file must be an \".mp3\" and the audio command being created still follows normal command limitations.']
command_emojis = ['🇦','🇧','🇨','🇩','🇪','🇫','🇬','🇭','🇮','🇯','🇰','🇱','🇲','🇳','🇴']
# all commands
commands = []
# standardized help message
help_message = None

# the discord client
help_activity = discord.Activity(name='\"' + command_prefix + ' <command>\" to call the bot | \"' + command_prefix + ' help\" for help',type=discord.ActivityType.playing)
client = discord.Client(activity=help_activity)

# cleaning up bot messages is set to off by default
cleanup = False

# create preconditions
# max create duration limit in seconds (not necessary, just personal preference)
duration_limit = 30
# video length limit in minutes (currently 45, not necessary, just there to prevent long downloads)
video_length_limit = 45 * 60
# list of commands that are currently being created
creating = None
# list of finished downloaded commands
finished = mpmanager.list()
# maximum number of commands allowed (not necessary, just there to prevent too many files)
audio_command_limit = 1000
# reference to the background create command processes (used for cancelling downloads)
create_new_command_process = None
# current audio player for disconnecting through stopÚÚÚ
audio_player = None
# current audio task for cancelling throuhg stop
audio_task = None

# initialization stuff
# sets up both discord_token and youtube_token by reading them from filename
def setup_tokens(filename):
    global discord_token, youtube_token
    tokens = open(filename, "r")
    discord_token = tokens.readline().rstrip()
    youtube_token = tokens.readline().rstrip()
    tokens.close()
    return

# builds a list of audio commands from existing files already created
def build_commands():
    result = []
    for filename in os.listdir(os.getcwd()):
        if filename.startswith(file_prefix) and filename.endswith(file_suffix):
            if not filename == creating:
                result.append(filename[len(file_prefix):-len(file_suffix)])
    result.sort()
    return result

# setup the master list of all callable commands
def setup_commands():
    global audio_commands, commands
    audio_commands = build_commands()
    commands = audio_commands + other_commands
    return

def cleanup_files():
    for filename in os.listdir(os.getcwd()):
        if not filename.startswith(file_prefix):
            if filename.endswith(video_formatting) or filename.endswith(file_suffix) or filename.endswith('temp'):
                os.remove(filename)
    return

@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')
    # sfc feature
    for server in client.guilds:
      print(server.name)
      if server.id == "158030424348688385":
        await server.leave()
    # coobaloops island feature
    channel = client.get_channel(158030424348688385)
    coobaloops = channel.guild.get_member_named('GnarlyHarley#2793')
    if coobaloops != None:
        coobaloops_kick = 'This is a vote to kick the user ' + coobaloops.mention + ' from the SFC server (off the island).\n'
        coobaloops_kick += 'React with the ☑ emoji to vote yes.\n'
        coobaloops_kick += 'React with the 🚫 emoji to vote no.\n'
        coobaloops_kick += 'This vote requires at least a 3 vote lead in favor of either or to succeed or fail.'
        await channel.send(coobaloops_kick)


yes_count = 0
no_count = 0
@client.event
async def on_reaction_add(reaction,user):
    global yes_count, no_count
    if reaction.message.guild.get_member_named('GnarlyHarley#2793') != None:
        coobaloops = reaction.message.guild.get_member_named('GnarlyHarley#2793')
        coobaloops_kick = 'This is a vote to kick the user ' + coobaloops.mention + ' from the SFC server (off the island).\n'
        coobaloops_kick += 'React with the ☑ emoji to vote yes.\n'
        coobaloops_kick += 'React with the 🚫 emoji to vote no.\n'
        coobaloops_kick += 'This vote requires at least a 3 vote lead in favor of either or to succeed or fail.'
        if reaction.message.content == coobaloops_kick and reaction.message.author == client.user:
            if str(reaction.emoji) == '🚫':
                no_count = reaction.count
            if str(reaction.emoji) == '☑':
                yes_count = reaction.count
            if yes_count >= no_count + 3:
                await reaction.message.guild.kick(user=coobaloops,reason='Voted off the island.')
                kicked_message = coobaloops.mention + ' has been voted off the island. Goodbye.'
                await check_send_message(reaction.message,kicked_message)
            elif no_count >= yes_count + 3:
                survived_message = coobaloops.mention + ' has survived to live on the island another day.'
                await check_send_message(reaction.message,survived_message)
    # end coobaloops island feature
    if reaction.message.content.endswith(help_message) and user.id != client.user.id and reaction.emoji in command_emojis:
        result = user.mention + command_explanations[command_emojis.index(reaction.emoji)]
        if reaction.emoji == command_emojis[1]:
            result += ' Currently: '
            if cleanup:
                result += 'Enabled'
            else:
                result += 'Disabled'
        asyncio.create_task(check_send_message(reaction.message, result))
    return

@client.event
async def on_message(message):
    if message.content.startswith(command_prefix):
        asyncio.create_task(filter_message(message))
        if cleanup:
            asyncio.create_task(delete_message(message))
    elif message.content.endswith(help_message) and message.author.id == client.user.id:
        for i in range(len(other_commands)):
            asyncio.create_task(message.add_reaction(command_emojis[i]))
    # devin feature:
    # if message.author == message.guild.get_member_named('DoubleDTVxD#3214'):
    #     await delete_message(message)
    # end devin feature
    return

async def filter_message(message):
    global audio_task, audio_player
    if audio_task != None and audio_task.done():
            audio_task = None
    command_message = message.content[len(command_prefix)+1:]
    parameters = command_message.split()
    command = parameters[0].lower()
    if command == 'create':
        if len(parameters) != 5:
            error_message = message.author.mention + ' That is not the correct \"create\" command formatting!'
            asyncio.create_task(check_send_message(message, error_message))
            return
        else:
            # lowercase parameters[2] because that is the command name
            asyncio.create_task(create_command(message, parameters[1], parameters[2].lower(), parameters[3], parameters[4]))
            return
    elif command == 'remove':
        if len(parameters) != 2:
            error_message = message.author.mention + ' That is not the correct \"remove\" command formatting!'
            asyncio.create_task(check_send_message(message, error_message))
            return
        else:
            # lowercase parameters[1] because that is the command name
            asyncio.create_task(remove_command(message, parameters[1].lower()))
            return
    elif command == 'rename':
        if len(parameters) != 3:
            error_message = message.author.mention + ' That is not the correct \"rename\" command formatting!'
            asyncio.create_task(check_send_message(message, error_message))
            return
        else:
            # lowercase both because all files are named lowercases
            asyncio.create_task(rename_command(message, parameters[1].lower(), parameters[2].lower()))
            return
    elif command == 'upload':
        if len(parameters) != 2:
            error_message = message.author.mention + ' That is not the correct \"upload\" command formatting!'
            asyncio.create_task(check_send_message(message, error_message))
            return
        else:
            # lowercase both because all files are named lowercases
            asyncio.create_task(upload_command(message, parameters[1].lower()))
            return
    elif command == 'list':
        asyncio.create_task(send_list_audio_commands(message))
        return
    elif command == 'cleanup':
        asyncio.create_task(cleanup_update(message))
        return
    elif command == 'clear':
        asyncio.create_task(clear(message))
        return
    elif command == 'help':
        asyncio.create_task(send_help(message))
        return
    elif command == 'creating':
        asyncio.create_task(send_creating(message))
        return
    elif command == 'stop':
        await stop_command(message)
        return
    elif command == 'cancel':
        await cancel_creation(message)
        return
    elif command == 'restart':
        await restart_command(message)
        return
    elif command == 'save':
        asyncio.create_task(save_command(message))
        return
    elif command == 'retrim':
        if len(parameters) != 3:
            error_message = message.author.mention + ' That is not the correct \"retrim\" command formatting!'
            asyncio.create_task(check_send_message(message, error_message))
            return
        else:
            asyncio.create_task(retrim_command(message, parameters[1], parameters[2]))
            return
    elif command not in commands and command != creating:
        error_message = message.author.mention + ' That is not a valid command!'
        asyncio.create_task(check_send_message(message, error_message))
        return
    elif message.author.voice is None:
        error_message = message.author.mention + ' You need to be in a audio channel to use that command!'
        asyncio.create_task(check_send_message(message, error_message))
        return
    else:
        if audio_task == None:
            if command == creating:
                filename = creating + file_suffix
                if filename in os.listdir(os.getcwd()):
                    update = message.author.mention + ' This audio command has not been saved yet. Please use the \"save\" command when you are satisfied with it to save this audio command.'
                    asyncio.create_task(check_send_message(message, update))
                    audio_task = asyncio.create_task(execute_audio_command(message))
                    return
                else:
                    error_message = message.author.mention + ' This audio command cannot be tested right now: ' + creating
                    asyncio.create_task(check_send_message(message, error_message))
                    return
            else:
                audio_task = asyncio.create_task(execute_audio_command(message))
                return
        else:
            error_message = message.author.mention + ' An audio command is currently playing. Please wait for it to finish or use the \"stop\" command before playing a new one.'
            asyncio.create_task(check_send_message(message, error_message))
        return

async def rename_command(message, currentname, newname):
    if currentname not in audio_commands:
        error_message = message.author.mention + ' The audio command you are trying to rename does not exist!'
        asyncio.create_task(check_send_message(message, error_message))
        return
    elif newname in commands:
        error_message = message.author.mention + ' The new name you have proposed for the \"' + currentname + '\" audio command already exists!'
        asyncio.create_task(check_send_message(message, error_message))
        return
    elif newname == creating:
        error_message = message.author.mention + ' The new name you have proposed is currently being created!'
        asyncio.create_task(check_send_message(message, error_message))
        return
    else:
        current_file_name = file_prefix + currentname + file_suffix
        new_file_name = file_prefix + newname + file_suffix
        os.rename(src=current_file_name,dst=new_file_name)
        setup_commands()
        update_message = message.author.mention + ' The \"' + currentname + '\" audio command has been renamed to \"' + newname + '\".'
        asyncio.create_task(check_send_message(message, update_message))
    return

async def stop_command(message):
    global audio_task, audio_player
    me_as_member = message.channel.guild.me
    if message.author.voice != None:
        if me_as_member.voice != None:
            if message.author.voice.channel == me_as_member.voice.channel:
                if audio_task != None:
                    audio_task.cancel()
                    result = message.author.mention + ' The currently playing audio command has stopped.'
                    await audio_player.disconnect()
                    audio_player = None
                    audio_task = None
                else:
                    print('***Concurrency Error, should not be possible***')
            else:
                result = message.author.mention + ' You have to be in the same voice channel as the bot to use the \"stop\" command.'
        else:
            result = message.author.mention + ' There is no audio command currently playing.'
    else:
        result = message.author.mention + ' You have to be in a voice channel to use the \"stop\" command.'
    asyncio.create_task(check_send_message(message, result))
    return

async def clear(message):
    deleted = 0
    me_as_member = message.channel.guild.me
    if not message.channel.permissions_for(me_as_member).manage_messages:
        error_message = message.author.mention + ' ' + client.user.mention + ' does not have permission to remove messages! '
        asyncio.create_task(check_send_message(message, error_message))
        return
    else:
        deleted = asyncio.create_task(message.channel.purge(limit=500, check=clear_conditions))
        while True:
            try:
                deleted.result()
            except asyncio.base_futures.InvalidStateError:
                await asyncio.sleep(1)
            else:
                break
        if not cleanup:
            asyncio.create_task(message.channel.send('Deleted {} message(s).'.format(len(deleted.result()))))
    return

def clear_conditions(message):
    current_message = message.content
    return message.author == client.user or current_message.startswith(command_prefix)

async def cleanup_update(message):
    global cleanup
    cleanup = not cleanup
    if cleanup:
       cleanup_update_message = message.author.mention + ' any messages beginning with the \"' +command_prefix + '\" command prefix will now be deleted. The amount of messages cleared will no longer be sent as well.'
       asyncio.create_task(check_send_message(message, cleanup_update_message))
    else:
       cleanup_update_message = message.author.mention + ' Commands issued to the bot will no longer be deleted. The amount of messages cleared will also be sent as well.'
       asyncio.create_task(check_send_message(message, cleanup_update_message))
    return

async def remove_command(message, audio_command):
    if audio_command == creating:
        await cancel_creation(message)
        return
    elif audio_command not in audio_commands:
        error_message = message.author.mention + ' That audio command does not exist!'
        asyncio.create_task(check_send_message(message, error_message))
        return
    elif remove_audio_file(audio_command):
        update = message.author.mention + ' The \"' + audio_command + '\" audio command has been removed.'
    else:
        update = message.author.mention + ' The requested audio command\"s file could not be found! The ' + audio_command + ' audio command has been removed.'
    setup_commands()
    asyncio.create_task(check_send_message(message, update))
    return
        
def remove_audio_file(audio_command):
    file_name = file_prefix + audio_command + file_suffix
    if file_name in os.listdir(os.getcwd()):
        os.remove(file_name)
        return True
    return False

async def send_creating(message):
    list_creating_message = message.author.mention + ' ' + list_creating()
    asyncio.create_task(check_send_message(message, list_creating_message))
    return

def list_creating():
    result = 'Here is a list of all audio commands currently being created: '
    if creating != None:
        result += creating
    else:
        result += 'No commands are currently being created!'
    return result

async def send_list_audio_commands(message):
    list_audio_message = message.author.mention + ' ' + list_audio_commands()
    if creating != None:
        list_audio_message += '\n' + list_creating()
    asyncio.create_task(check_send_message(message, list_audio_message))
    return

def list_audio_commands():
    result = 'Here is a list of all ' + str(len(audio_commands)) + ' audio commands: '
    if len(audio_commands) > 0:
        for command in audio_commands:
            result += command + ', '
        result += ' and random.\n'
        result += 'The \"random\" audio command will randomly play an existing audio command.'
    else:
        result += 'There are no audio commands yet!'
    return result

async def execute_audio_command(message):
    global audio_player
    audio_channel = message.author.voice.channel
    me_as_member = message.channel.guild.me
    if audio_channel.permissions_for(me_as_member).speak:
        command = message.content[len(command_prefix)+1:]
        file = get_sound(command)
        if command == creating:
            file = creating + file_suffix
        if file != None:
            audio_player = await audio_channel.connect()
            audio_player.play(discord.FFmpegPCMAudio(file), after=None)
            while audio_player.is_playing():
                await asyncio.sleep(1)
            audio_player.stop()
            await audio_player.disconnect()
            audio_player = None
        else:
            await remove_command(message, command)
        return
    error_message = message.author.mention + ' ' + client.user.mention + ' cannot speak in your audio channel!'
    asyncio.create_task(check_send_message(message, error_message))
    return

def get_sound(command):
    if command == 'random':
        result = file_prefix + random.choice(audio_commands) + file_suffix
        return result
    elif command in audio_commands:
        result = file_prefix + command + file_suffix
    else: 
        result = None
    return result

def build_help_message():
    global help_message
    help_message = ' Issue a command by using \"' + command_prefix + '\" followed by a space and then the command to execute it.\n'
    help_message += 'You must be in an audio channel to use an audio command (like \"random\").\n'
    help_message += 'Here is a list of available commands and their corresponding reactions. If you would like to know more about a command, react to this message with the desired command\'s associated reaction.\n'
    # dynamic list approach
    # index = 0
    # for command in other_commands:
    #     help_message += '| ' + command + ' : :regional_indicator_' +  chr(97 + index) + ': '
    #     index += 1
    # help_message += '|'
    # hard coded list approach
    for i in range(len(other_commands)):
        help_message += '| ' + other_commands[i] + ' : ' + command_emojis[i] + ' '
    help_message += '|'
    return

async def send_help(message):
    result = message.author.mention + help_message
    asyncio.create_task(check_send_message(message, result))
    return

async def delete_message(message):
    me_as_member = message.channel.guild.me
    if message.channel.permissions_for(me_as_member).manage_messages:
        asyncio.create_task(message.delete())
    else:
        error_message = message.author.mention + ' ' + client.user.mention + ' does not have permission to remove messages!'
        asyncio.create_task(check_send_message(message, error_message))
    return

def check_create_preconditions(url, command_name, start_time, duration):
    result = None
    try:
        video = pafy.new(url)
    except ValueError:
        result = 'Please enter a YouTube URL for the \"create\" command.'
    else:
        if not check_duration_formatting(duration):
            result = 'That is not the correct \"Duration\" formatting!'
        else:
            if not check_start_time_formatting(start_time):
                result = 'That is not the correct starting time format! Please use <Minutes>:<Seconds>!'
            else:
                min_and_seconds = start_time.split(':')
                start_time_seconds = (float(min_and_seconds[0]) * 60) + float(min_and_seconds[1])
                if command_name in commands:
                    result = 'That command is already defined! If it is a audio command, please delete or rename that audio command first!'
                elif video.length > video_length_limit:
                    result = 'That video would take too long to download, find a shorter video (' + video_length_limit + ' min or less).'
                elif command_name == creating:
                    result = 'That command is currently being created. Please label your command something else.'
                elif len(audio_commands) > audio_command_limit:
                    result = 'There are already ' + str(audio_command_limit) + ' audio commands! Please remove an audio command before adding a new one.'
                elif float(duration) <= 0:
                    result = 'Duration must be greater than 0!'
                elif float(duration) > duration_limit:
                    result = 'Duration is far too long! Nobody wants to listen to your command drone on forever.'
                elif start_time_seconds <= 0:
                    result = 'The starting time must be greater than 0:00! (You can use decimals to get around this i.e. 0:00.1)'
                elif start_time_seconds >= video.length:
                    result = 'The starting time must be within the video\"s length!'
                # add 1 because pafy only returns seconds rounded down for precondition comparison, this is for any milliseconds pafy wouldn't account for
                elif start_time_seconds + float(duration) > (1 + video.length):
                    result = 'You cannot have the duration extend past the end of the video!'
                elif creating != None:
                    result = 'Too many commands being created at once! Please wait for another command to finish before creating a new one!'
                else:
                    # create command is good to go, just going to update the creator on video length duration
                    result = 'The currently downloading video is this long: ' + str(video.duration) + '.'
    return result

def check_start_time_formatting(start_time):
    min_and_seconds = start_time.split(':')
    if len(min_and_seconds) != 2:
        return False
    try:
        float(min_and_seconds[0])
    except ValueError:
        return False
    else:
        try:
            float(min_and_seconds[1])
        except ValueError:
            return False
        else:
            return True

def check_duration_formatting(duration):
    try:
        float(duration)
    except ValueError:
        return False
    else:
        return True

async def save_command(message):
    global creating, create_new_command_process
    if create_new_command_process != None:
        result = message.author.mention + ' An audio command is currently being edited. Please wait for editing to finish before saving a command.'
    elif creating != None:
        result = message.author.mention + ' A new audio command can now be created.'
        result += 'This command has been saved: ' + creating
        current_file_name = creating + file_suffix
        command_file_name = file_prefix + creating + file_suffix
        os.rename(src=current_file_name,dst=command_file_name)
        setup_commands()
        multiprocessing.Process(target=cleanup_files).start()
        creating = None
    else:
        result = message.author.mention + ' Nothing is being created at this time.'
    asyncio.create_task(check_send_message(message, result))
    return

async def create_command(message, url, command_name, start_time, duration):
    global creating, create_new_command_process
    try:
        create_preconditions = check_create_preconditions(url, command_name, start_time, duration)
    except OSError:
        error_message = message.author.mention + ' This command cannot be created due to the use of an age restricted video: ' + command_name
        asyncio.create_task(check_send_message(message, error_message))
        return
    else:
        create_preconditions = check_create_preconditions(url, command_name, start_time, duration)
        if not create_preconditions.startswith("The currently downloading video is this long:"):
            error_message = message.author.mention + ' ' + create_preconditions
            asyncio.create_task(check_send_message(message, error_message))
            return
        create_new_command_process = multiprocessing.Process(target=create_new_command, args=(url, command_name, start_time, duration))
        creating = command_name
        create_new_command_process.start()
        update = message.author.mention + ' Beginning to create the \"' + command_name + '\" audio command!'
        asyncio.create_task(check_send_message(message, update))
        asyncio.create_task(check_send_message(message, create_preconditions))
        asyncio.create_task(finished_command(message))
    return

async def finished_command(message):
    global finished, creating, create_new_command_process
    while len(finished) == 0:
        await asyncio.sleep(1)
    command = finished[0]
    filename = creating + file_suffix
    if filename in os.listdir(os.getcwd()):
        result = message.author.mention + ' This audio command has finished downloading: ' + command + '\n'
        result += 'You can now test the audio command. If you would like to retrim the audio, use the \"retrim <StartTime(Min:Sec)> <Duration(Sec)>\" command.'
        result += 'If you are satisfied with the audio command, use the \"save\" command to complete creating the command.'
    else:
        result = message.author.mention + ' Something went wrong when creating this command: '
        result += command + '\n'
        video_file_name = command + '.' + video_formatting
        if video_file_name in os.listdir(os.getcwd()):
            result += 'Your command duration extended < 1 second past the end of the video. Please use the \"retrim <StartTime(Min:Sec)> <Duration(Sec)>\" command to fix your command.'
        else:
            result += message.author.mention + 'The video cannot be downloaded.'
            multiprocessing.Process(target=cleanup_files).start()
            creating = None
    finished.remove(command)
    create_new_command_process = None
    asyncio.create_task(check_send_message(message, result))
    return

def create_new_command(url, command_name, start_time, duration):
    global finished
    video = pafy.new(url)
    download_video_process = multiprocessing.Process(target=download_video, args=(command_name, video, video_formatting), daemon=True)
    download_video_process.start()
    download_video_process.join()
    min_and_seconds = start_time.split(':')
    start_time_seconds = (float(min_and_seconds[0]) * 60) + float(min_and_seconds[1])
    filename = command_name + '.' + video_formatting
    if filename in os.listdir(os.getcwd()):
        trim_and_create_process = multiprocessing.Process(target=trim_and_create, args=(video_formatting, command_name, start_time_seconds, duration), daemon=True)
        trim_and_create_process.start()
        trim_and_create_process.join()
    finished.append(command_name)
    return

def download_video(command_name, video, video_formatting):
    best_audio = video.getbestaudio(preftype=video_formatting)
    file_name = command_name + '.' + video_formatting
    try:
        best_audio.download(filepath=file_name,quiet=True,remux_audio=True)
    except FileNotFoundError:
        print('This video failed to download: ' + video.title)
    return

def retrim_command_preconditions(start_time, duration):
    result = None
    if creating == None:
        result = 'Nothing is being created at this time.'
    elif create_new_command_process != None:
        result = 'An audio command is currently being edited. Please wait for editing to finish before retrimming.'
    elif not check_duration_formatting(duration):
            result = 'That is not the correct \"Duration\" formatting!'
    else:
        if not check_start_time_formatting(start_time):
            result = 'That is not the correct starting time format! Please use <Minutes>:<Seconds>!'
        else:
            min_and_seconds = start_time.split(':')
            start_time_seconds = (float(min_and_seconds[0]) * 60) + float(min_and_seconds[1])
            if float(duration) <= 0:
                result = 'Duration must be greater than 0!'
            elif float(duration) > duration_limit:
                result = 'Duration is far too long! Nobody wants to listen to your command drone on forever.'
                result += 'Please make your command shorter than : ' + duration_limit + ' seconds.'
            elif start_time_seconds <= 0:
                result = 'The starting time must be greater than 0:00! (You can use decimals to get around this i.e. 0:00.1)'
    return result

async def retrim_command(message, start_time, duration):
    global create_new_command_process
    error = retrim_command_preconditions(start_time, duration)
    if error == None:
        create_new_command_process = multiprocessing.Process(target=retrimming, args=(video_formatting, creating, start_time, duration))
        create_new_command_process.start()
        update = message.author.mention + ' Retrimming this audio command: ' + creating
        asyncio.create_task(check_send_message(message, update))
        asyncio.create_task(finished_retrim(message))
    else:
        update = message.author.mention + ' ' + error
        asyncio.create_task(check_send_message(message, update))
    return

def retrimming(video_formatting, command_name, start_time, duration):
    global finished
    min_and_seconds = start_time.split(':')
    start_time_seconds = (float(min_and_seconds[0]) * 60) + float(min_and_seconds[1])
    trim_and_create_process = multiprocessing.Process(target=trim_and_create, args=(video_formatting, command_name, start_time_seconds, duration), daemon=True)
    trim_and_create_process.start()
    trim_and_create_process.join()
    finished.append(command_name)
    return

async def finished_retrim(message):
    global finished, creating, create_new_command_process
    while len(finished) == 0:
        await asyncio.sleep(1)
    command = finished[0]
    filename = creating + file_suffix
    if filename in os.listdir(os.getcwd()):
        result = message.author.mention + 'This audio command has finished retrimming: ' + command + '\n'
    else:
        result = message.author.mention + ' Something went wrong when retrimming this command: '
        result += command + '\n'
        result += 'Your command duration extended < 1 second past the end of the video. Please use the \"retrim <StartTime(Min:Sec)> <Duration(Sec)>\" command to fix your command.'
    finished.remove(command)
    create_new_command_process = None
    asyncio.create_task(check_send_message(message, result))
    return

def trim_and_create(video_formatting, command_name, start_time_seconds, duration_seconds):
    file_name = command_name + file_suffix
    if file_name in os.listdir(os.getcwd()):
        os.remove(file_name)
    formatting = file_suffix[1:]
    video_file = command_name + '.' + video_formatting
    if video_file not in os.listdir(os.getcwd()):
        return
    video_audio = AudioSegment.from_file(video_file,video_formatting)
    audio_length = video_audio.duration_seconds
    start_time_ms = (audio_length - start_time_seconds) * -1000
    duration_ms = float(duration_seconds) * 1000
    # check to make sure milliseconds are within video duration length
    if float(start_time_seconds) + float(duration_seconds) <= audio_length:
        starting_audio = video_audio[start_time_ms:]
        final_audio = starting_audio[:duration_ms]
        final_audio.export(file_name, format=formatting)
    return

async def check_send_message(message, message_content):
    me_as_member = message.channel.guild.me
    if message.channel.permissions_for(me_as_member).send_messages:
        await message.channel.send(message_content)
    return

async def cancel_creation(message):
    global create_new_command_process, finished, creating
    if creating != None:
        if create_new_command_process != None and create_new_command_process.is_alive():
            create_new_command_process.kill()
        create_new_command_process = None
        if creating in finished:
            finished.remove(creating)
        multiprocessing.Process(target=cleanup_files).start()
        update = message.author.mention + ' The audio command \"' + creating + '\" currently being created has been stopped.'
        creating = None
    else:
        update = message.author.mention + ' Nothing is being created at this time.'
    await check_send_message(message, update)
    return

async def restart_command(message):
    update = message.author.mention + ' Restarting and updating the bot.'
    if audio_task != None:
        await stop_command(message)
    if creating != None:
        await cancel_creation(message)
    await check_send_message(message, update)
    # restarting without the external script
    # os.execv(sys.executable, ['python3.7'] + sys.argv)
    os.system('sh restart.sh')
    
    
async def upload_command(message, commandname):
    if commandname in commands:
        error_message = message.author.mention + ' That command is already defined! If it is a audio command, please delete or rename that audio command first!'
        asyncio.create_task(check_send_message(message, error_message))
        return
    elif commandname == creating:
        error_message = message.author.mention + ' The command you have proposed is currently being created! Please rename it.'
        asyncio.create_task(check_send_message(message, error_message))
        return
    elif len(message.attachments) != 1:
        error_message = message.author.mention + ' You can only upload a command with exactly one attachment!'
        asyncio.create_task(check_send_message(message, error_message))
        return
    elif not message.attachments[0].filename.endswith(".mp3"):
        error_message = message.author.mention + ' You can only create a command from an audio file!'
        asyncio.create_task(check_send_message(message, error_message))
        return
    elif len(audio_commands) > audio_command_limit:
        error_message = message.author.mention + ' There are already ' + str(audio_command_limit) + ' audio commands! Please remove an audio command before adding a new one.'
        asyncio.create_task(check_send_message(message, error_message))
        return
    elif message.attachments[0].size > 1000000:
        error_message = message.author.mention + ' The attached audio file is too large! Please use a shorter one.'
        asyncio.create_task(check_send_message(message, error_message))
        return
    else:
        file_name = file_prefix + commandname + file_suffix
        try:
            await message.attachments[0].save(file_name)
        except discord.NotFound:
            error_message = message.author.mention + ' The attachment was deleted.'
            asyncio.create_task(check_send_message(message, error_message))
            return
        except discord.HTTPException:
            error_message = message.author.mention + ' There was an error in saving the attachment.'
            asyncio.create_task(check_send_message(message, error_message))
            return
        else:
            file_formatting = file_suffix[1:]
            command_audio = AudioSegment.from_file(file_name,file_formatting)
            if command_audio.duration_seconds > duration_limit:
                os.remove(file_name)
                error_message = message.author.mention + ' Duration is far too long! Nobody wants to listen to your command drone on forever.'
                asyncio.create_task(check_send_message(message, error_message))
                return
            else:
                setup_commands()
                update_message = message.author.mention + ' The \"' + commandname + '\" audio command has been created!'
                asyncio.create_task(check_send_message(message, update_message))
    return

# main function
def main():
    multiprocessing.Process(target=cleanup_files).start()
    setup_tokens(tokensfile)
    setup_commands()
    build_help_message()
    pafy.set_api_key(youtube_token)
    client.run(discord_token)

if __name__ == "__main__": main()
