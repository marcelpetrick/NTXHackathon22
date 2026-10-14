Hacktoberfest 2022 → 2026: 𝐭𝐡𝐞 𝐰𝐨𝐫𝐥𝐝'𝐬 𝐬𝐥𝐨𝐰𝐞𝐬𝐭 𝐩𝐫𝐨𝐭𝐨𝐭𝐲𝐩𝐞 now works

October was always some kind of #Hacktoberfest. Four years ago I joined a hackathon with Shuhong and Tom, where we tried to get any of the provided brain-computer interfaces to work. It was nice that such an event was organized by the @TUM. I guess there is also a really old post about this here on LinkedIn.

Anyway: at that time we spent most of the time configuring and getting familiar with the hardware and the whole workflow, instead of building a final prototype. So around noon on Sunday we decided to capture some "𝐜𝐨𝐧𝐭𝐫𝐨𝐥 𝐄𝐄𝐆". I never got around to processing them and testing them against the idea of controlling 𝐏𝐚𝐜𝐦𝐚𝐧 with them. But since I came across this GitHub repo while cleaning up, I thought: 𝐰𝐡𝐲 𝐧𝐨𝐭 𝐧𝐨𝐰?

So, here it is. One stream contained ten blink signals (with the eyes), which were recorded by the #OpenBCI Ganglion, the BCI (brain computer interface) board we used at that time.
They are recognizable by a filter: a 0.5–10 Hz band-pass, averaged over the four channels, then a robust z-score threshold (median/MAD) that picks the big peaks. Then those impulses are used to control Pacman. As you can see, the result is not optimal and not suited to really "play" that one-dimensional game. But it shows the whole end-to-end workflow.

Now updated on GitHub as a repo, with the tooling, the recorded test data and also the end-to-end connection: GitHub -> marcelpetrick -> NTXHackathon22
https://github.com/marcelpetrick/NTXHackathon22

If you have question, ask. Of course, this is not Neuralink ;)
