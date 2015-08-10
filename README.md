# Rhythm
Rhythm is an IRC bot designed to help you run meetings.

It's designed to let channel ops put forth motions and to have the channel vote on them.


## Installation

Initial installation and launch:

1. Install [Python 3.4](https://www.python.org/downloads/).
2. `git clone https://github.com/KnightHawk3/Rhythm.git`
3. `cd Rhythm`
4. `pyvenv env`
5. `source env/bin/activate`
6. `pip3 install -r requirements.txt`
7. `cp config.orig.ini config.ini`

Make your modifications to the config file (`config.ini`) using your preferred editor. After this, you can launch Rhythm with the following command:

```
irc3 config.ini
```


## Launching

1. `cd Rhythm`
2. `source env/bin/activate`
3. `irc3 config.ini`


## Getting Started

* Op the bot. Do it.
* Start a meeting with the following commands in the channel:

```
<@coolguy> !start meeting
<@coolguy> !quorum 42
```

* Voice users who should be able to vote.
* The `!add <nick>` command tells Rhythm to re-op that user whenever they rejoin.
* Start a motion:

```
<@coolguy> !motion Give everyone a high-five!
<@coolguy> !start motion
```

* Recognised people (ops, voiced) can say `aye`, `nay`, or `abstain` to cast their votes.
* Ops may add votes from an external source, such as physical delegates in a room, using commands such as `!ayes 37` and `!nays 12`.
* To stop the motion and tally results:

```
<@coolguy> !stop motion
```

* To cancel a motion for any reason:

```
<@coolguy> !cancel motion
```

* To end the meeting, kill the bot or:

```
<@coolguy> !stop meeting
```


## License

Licensed under the MIT License, detailed in the `LICENSE` file.
