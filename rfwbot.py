#!/usr/bin/env python3
import discord, configparser, random, re, requests, random
from time import sleep

class InvalidDieException(Exception):
    def __init__(self, die, error='invalid'):
        self.die = die
        self.error = error
    def __str__(self):
        if self.error == 'too many die':
            return "Error: Too many die. Slow your roll."
        if self.error == 'too many sides':
            return "Error: IT'S OVER 9000!!!!1!11!11!one!!11"
        else:
            return "Error: Invalid Die: " + self.die


class DiscordBot:
    def __init__(self, configFile):
        self._loadConfig(configFile)
        self.cReload()

    def _loadConfig(self, configFile):
        self.config = configparser.ConfigParser()
        self.config.read(configFile)
        self.commandString = self.config.get(
            'settings', 'commandString', fallback='!'
        )

    def cReload(self):
        self.loadCommands()
        self.loadChannels()
        self.loadAdmins()
        self.loadIgnore()


    def loadCommands(self):
        self.commands = {}
        commandsFile = self.config.get(
            'files', 'commands', fallback='commands.txt'
        )

        f = open(commandsFile, 'r')

        commandGroup = ''

        for line in f:
            # Detect beginning of new commandGroup, "[[name]]"
            m = re.match('\[\[(.*)\]\]', line)
            if m:
                commandGroup = m.group(1)
                self.commands[commandGroup] = {}
                continue

            # If no current commandGroup is set, ignore this line
            if not commandGroup:
                continue

            (command, response) = line.split("\t", 1)
            if command in self.commands[commandGroup]:
                self.commands[commandGroup][command].append(response.strip())

            else:
                self.commands[commandGroup][command]=[response.strip()]

        f.close()


    def loadChannels(self):
        channelsFile = self.config.get(
            'files', 'channels', fallback='channels.txt'
        )
        f = open(channelsFile, 'r')

        self.commandGroups = {}

        for line in f:
            (channelId, commandGroups) = line.split("\t", 1)
            self.commandGroups[channelId] = commandGroups.strip().split(",")

        f.close()


    def loadAdmins(self):
        self.admins=[]

        adminsFile = self.config.get(
            'files', 'admins', fallback='admins.txt'
        )
        f = open(adminsFile, 'r')

        for line in f:
            id = line.strip()
            if id != '': self.admins.append(id)


        f.close()

    def loadIgnore(self):
        self.ignore=[]

        ignoreFile = self.config.get(
            'files', 'ignore', fallback='ignore.txt'
        )
        f = open(ignoreFile, 'r')

        for line in f:
            id = line.strip()
            if id != '': self.ignore.append(id)


        f.close()

    def handleLogin(self, user):
        print('Logged in as {}'.format(user.name))
        self.user = user


    def connect(self):
        self.client = discord.Client()
        self.client.login(
            self.config['authentication']['username'],
            self.config['authentication']['password']
        )
        return self.client


    def isAdmin(self, user):
        return user.id in self.admins


    def isIgnored(self, user):
        return (user.id in self.ignore or user == self.user)


    async def say(self, channel, message):
        print('\033[1;34m[\033[31m' + str(channel) + '\033[34m]\033[32m Replying ...\033[0m')
        # print('\033[1;34m[\033[0;31;1m' + str(channel) + '\033[1;34m]\033[0;32m Replying\033[0;33;1m: \033[0;32;1m' + str(message) + '\033[0;32m')
        await self.client.send_message(channel, message)
        sleep(1)


    async def handleCommand(self, channel, message, sender):
        # Are we listening in this channel?
        if channel.id not in self.commandGroups:
            return

        # Get the list of commandGroups for this channel
        commandGroups = self.commandGroups[channel.id]

        # Working backwards from the end of the string, remove
        # words until a command is found
        cmd = message.strip()
        params = ''
        response = False
        while True:
            rawResponse = self.getRawCommandResponse(commandGroups, cmd.strip(), params.strip())
            if rawResponse != False:
                break

            spl = cmd.rsplit(' ',1)
            if len(spl) == 1:
                break
            cmd = spl[0]
            params = spl[1] + ' ' + params

        if rawResponse != False:
            await self.processCommandResponse(channel, rawResponse, sender, params.strip())


    def getRawCommandResponse(self, commandGroups, cmd, params):
        # Single-spacify the command
        cmd = ' '.join(cmd.split()).lower()

        # Iterate over all commandGroups for the current channel
        for g in commandGroups:
            if g in self.commands:
                if cmd in self.commands[g] and params == '':
                    # Exact command match with no params
                    return random.choice(self.commands[g][cmd])

                elif (cmd + ' *') in self.commands[g] and params != '':
                    return random.choice(self.commands[g][cmd + ' *'])

        # We got to here with no result, so there is no matching command
        return False


    async def processCommandResponse(self, channel, response, sender, params):
        if "%LIST%" in response:
            # Need to get a list of subkeys. Out of scope right now.
            response = response.replace(
                "%LIST%", "This function is not yet implemented"
            )

        if "%SENDER%" in response:
            response = response.replace("%SENDER%", sender.name)

        if "%INPUT%" in response:
            response = response.replace("%INPUT%", params)

        if "%CHOICE%" in response:
            response = response.replace(
                "%CHOICE%",
                random.choice(params.split(',')).strip()
            )

        if "%ROLL%" in response:
            try:
                response = response.replace(
                    "%ROLL%",
                    self.diceRoll(params)
                )
            except InvalidDieException as e:
                response = str(e)

        if "%XKCD%" in response:
            response = response.replace("%XKCD%", self.getXkcd(params))

        if "%RANDOM_XKCD%" in response:
            response = response.replace("%RANDOM_XKCD%", self.getRandomXkcd())


        await self.say(channel, response)


    def diceRoll(self, dice):
        dice = dice.split()
        rolls = []
        for die in dice:
            dieDef = die.lower().split('d')
            if len(dieDef) != 2:
                raise InvalidDieException(die)
            try:
                if dieDef[0] == '':
                    number = 1
                else:
                    number = int(dieDef[0])

                sides = int(dieDef[1])
            except ValueError:
                raise InvalidDieException(die)

            if number < 1 or sides < 2:
                raise InvalidDieException(die)

            if number > 20:
                raise InvalidDieException(die, 'too many die')

            if sides > 9000:
                raise InvalidDieException(die, 'too many sides')

            for i in range(number):
                rolls.append(random.randint(1,sides))

        return " + ".join(str(n) for n in rolls) + (" = " + str(sum(rolls)) if len(rolls) > 1 else '')


    def getXkcd(self,number):
        try:
            r = requests.get("http://xkcd.com/{}/info.0.json".format(number))
        except:
            return "Sorry, I couldn't reach XKCD"

        try:
            title = r.json()['safe_title']
        except:
            return("Comic {} not found".format(number))

        return("http://xkcd.com/{} (\"{}\")".format(number, title))


    def getRandomXkcd(self):
        try:
            r = requests.get("http://xkcd.com/info.0.json")
            latest = r.json()['num']
        except:
            return "Sorry, I couldn't reach XKCD"

        return self.getXkcd(random.randint(1, latest))


    async def handleSystemCommand(self, channel, message, sender):
        print(self.isAdmin(sender))
        print(channel.is_private)
        # if not channel.is_private: return

        (cmd, params) = (message.strip() + ' ').split(' ', 1)
        cmd = cmd.lower()

        # General commands

        if cmd == 'whoami':
            await self.say(channel, 'Your name is {} and your id is {}'
                .format(sender.name, sender.id))

        # Admin commands

        if not self.isAdmin(sender): return

        if cmd == 'reload':
            self.cReload()
            await self.say(channel, 'Reloaded!')
        if cmd == 'stop':
            await self.say(channel, 'Shutting down.')
            self.client.logout()
        if cmd == 'channels':
            await self.say(channel, 'Channel list:')
            for s in self.client.servers:
                await self.say(channel, 'Server: {}\n'.format(s.name))
                for c in s.channels:
                    if str(c.type) == 'text':
                        r = "-- {} (id: {})\n".format(
                            c.name, c.id
                        )
                        if c.id in self.commandGroups:
                            r += "---- In groups: {}\n".format(
                                ', '.join(self.commandGroups[c.id])
                            )
                        else:
                            r += "---- (Channel not monitored)\n"
                        await self.say(channel, r)



rfwbot = DiscordBot('config/rfwbot.conf')
client = rfwbot.connect();

@client.async_event
async def on_message(message):
    print('\033[1;34m[\033[31m' + str(message.channel) + '\033[34m]\033[36m ' + str(message.author) + '\033[33m: \033[0m' + str(message.content))
    # say = input('--> ')

    if not rfwbot.isIgnored(message.author):
        if message.content.startswith(rfwbot.commandString):
            command = message.content[len(rfwbot.commandString):]
            print('\033[1;34m[\033[31m' + str(message.channel) + '\033[34m]\033[31m Command Detected\033[033m: \033[0;33m' + command + '\033[0m')
            if command.startswith(rfwbot.commandString):
                # System commands start with !!
                command = command[len(rfwbot.commandString):]
                await rfwbot.handleSystemCommand(message.channel, command, message.author)
            else:
                await rfwbot.handleCommand(message.channel, command, message.author)

        # Table Flip Correction
        elif '︵ ┻━┻' in message.content or \
            '︵  ┻━┻' in message.content or \
            '┻━┻ ︵' in message.content or \
            '┻━┻  ︵' in message.content or \
            '︵ ┻─┻' in message.content or \
            '︵  ┻─┻' in message.content or \
            '┻─┻ ︵' in message.content or \
            '┻─┻  ︵' in message.content or \
            '︵ ┴━┴' in message.content or \
            '︵  ┴━┴' in message.content or \
            '┴━┴ ︵' in message.content or \
            '┴━┴  ︵' in message.content or \
            '︵ ┴─┴' in message.content or \
            '︵  ┴─┴' in message.content or \
            '┴─┴ ︵' in message.content or \
            '┴─┴  ︵' in message.content:
            print('\033[1;34m[\033[31m' + str(message.channel) + '\033[34m]\033[31m Table Flip Detected\033[0m')
            msg  = ''
            for x in range(0, sum(message.content.count(y) for y in ('︵ ┻━┻', '︵  ┻━┻', '┻━┻ ︵', '┻━┻  ︵', '︵ ┻─┻', '︵  ┻─┻', '┻─┻ ︵', '┻─┻  ︵', '︵ ┴━┴', '︵  ┴━┴', '┴━┴ ︵', '┴━┴  ︵', '︵ ┴─┴', '︵  ┴─┴', '┴─┴ ︵', '┴─┴  ︵'))):
                if x != 0:
                    msg += ' '

                msg += '┳━┳ノ(°-°ノ)'

            await rfwbot.say(message.channel, msg)

        # FiBot Source Reply
        elif 'fibot' in message.content.lower() and 'source' in message.content.lower():
            print('\033[1;34m[\033[31m' + str(message.channel) + '\033[34m]\033[31m Bot Source Detected\033[0m')
            await rfwbot.say(message.channel, 'You can view my source or fork and submit a pull request at: https://github.com/eliasthompson/ZUbot')

        # This is fine Reply
        elif 'this is fine' in message.content.lower():
            print('\033[1;34m[\033[31m' + str(message.channel) + '\033[34m]\033[31m This is Fine Detected\033[0m')
            await rfwbot.say(message.channel, 'http://i.imgur.com/c4jt321.png')

        # Fi Reply
        elif ':fi:' in message.content.lower() or \
            'fi should' in message.content.lower() or \
            'fi can' in message.content.lower() or \
            'fi will' in message.content.lower() or \
            'fi would' in message.content.lower() or \
            'fi do' in message.content.lower() or \
            'fi are' in message.content.lower() or \
            'fi is' in message.content.lower() or \
            'fi did' in message.content.lower() or \
            'fi what' in message.content.lower() or \
            'fi who' in message.content.lower() or \
            'fi where' in message.content.lower() or \
            'fi how' in message.content.lower() or \
            'fi when' in message.content.lower() or \
            'fi if' in message.content.lower() or \
            'fi why' in message.content.lower() or \
            'fi?' in message.content.lower() or \
            'fi am' in message.content.lower():
            print('\033[1;34m[\033[31m' + str(message.channel) + '\033[34m]\033[31m Fi Detected\033[0m')

            responses = [
                '<:fi:281601396581597204> I predict an 85% chance you will find my results helpful.',
                '<:fi:281601396581597204> Signs indicate a 75% chance that it is unlikely.',
                '<:fi:281601396581597204> I calculate an 85% chance you can obtain information about it by asking Slackbot instead.',
                '<:fi:281601396581597204> 80% of the room itself is covered in a blanket of sand.',
                '<:fi:281601396581597204>  I calculate a 75% probability that visiting the fortune-teller will be helpful.',
                '<:fi:281601396581597204> There is a 95% probability that you will discover something unexpected.',
                '<:fi:281601396581597204> There is an 85% probability that any eventual results will be of use, Master.',
                '<:fi:281601396581597204> I estimate you have less than a 1% chance of completing your quest.',
                '<:fi:281601396581597204> I judge the probability of defeat at 30%.',
                '<:fi:281601396581597204> He increased his muscle mass by 500%.',
                '<:fi:281601396581597204> Over 80% of ghosts are said to harbor some kind of unfulfilled desire.',
                '<:fi:281601396581597204> Sensitivity to human presence: 60%.',
                '<:fi:281601396581597204> I project a 50% probability of failing.',
                '<:fi:281601396581597204> You can expect at least an 85% chance that it will attempt to stab you.',
                '<:fi:281601396581597204> I calculate the probability of your intense aggravation at 100%.',
                '<:fi:281601396581597204> I calculate a 100% failure rate.',
                '<:fi:281601396581597204> There is an 85% chance that something very important will occur here.',
                '<:fi:281601396581597204> I calculate a 60% chance that a portion of the information contained in my analysis will be new to you.',
                '<:fi:281601396581597204> I calculate a 95% chance your clothing will immediately combust upon entrance.',
                '<:fi:281601396581597204> I can verify with only 40% accuracy that this person is a plant.',
            ]

            await rfwbot.say(message.channel, responses[random.randint(0, (len(responses) - 1))])

        # Elias Emoji Reply
        elif ':elias:' in message.content.lower():
            print('\033[1;34m[\033[31m' + str(message.channel) + '\033[34m]\033[31m Elias Emoji Detected\033[0m')

            responses = [
                '<:elias:268180756306722832> There will be cake',
                '<:elias:268180756306722832> Twilight Princess is a Wii game',
            ]

            await rfwbot.say(message.channel, responses[random.randint(0, (len(responses) - 1))])

        # Sonic Emoji Reply
        elif 'sonic' in message.content.lower() or \
            'sanic' in message.content.lower() or \
            'sonac' in message.content.lower() or \
            'fast' in message.content.lower() or \
            'slow' in message.content.lower():
            print('\033[1;34m[\033[31m' + str(message.channel) + '\033[34m]\033[31m Sonic Detected\033[0m')

            responses = [
                '<:sonic:281605314111995905> GOTTA GO FAST',
                '<:sonic:281605314111995905> YOU\'RE TOO SLOW',
                '<:sonic:281605314111995905> COME ON, STEP IT UP',
                '<:sonic:281605314111995905> NOW I\'LL SHOW YOU',
                '<:sonic:281605314111995905> TRUE FAST ISN\'T MEASURED IN MILES, IT COMES FROM THE HEART',
                '<:sonic:281605314111995905> SONIC\'S THE NAME, SPEED\'S MY GAME',
                '<:sonic:281605314111995905> YOOLO SWAG',
            ]

            await rfwbot.say(message.channel, responses[random.randint(0, (len(responses) - 1))])


@client.async_event
def on_ready():
    rfwbot.handleLogin(client.user)


client.run(rfwbot.config['authentication']['password'])
