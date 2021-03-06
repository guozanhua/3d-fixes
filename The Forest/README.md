The Forest
==========

**Fix updated 2015-04-19 for the 0.16 Unity 5 update**

Note that the Unity 5 update is basically an entirely new fix from scratch and
is still an early work in progress. The Unity 5 update has made the issues with
the sun shafts and sun/moon glow more apparent and will need further work to
fix. Additionally, there are some halo issues with lights shining on water
(lightning, cannibal flashlights) that I have yet to fix.

Download the appropriate fix for your version:

- Unity 4 (for The Forest 0.15): <https://s3.amazonaws.com/DarkStarSword/3Dfix-The+Forest-2014-12-03.zip>
- Unity 5 (for The Forest 0.16): <https://s3.amazonaws.com/DarkStarSword/3Dfix-The+Forest-2015-04-19.zip>

Installation Instructions
-------------------------
1. Extract the zip file to the game directory
2. Turn off motion blur (the game doesn't currently save settings, so you have
   to do this every time)

Fixed
-----
- Halos on all surfaces
- Light, shadows and specular highlights
- Water (some issues with lights & reflections remain)
- Certain UI elements that were drawn at screen depth pushed back (e.g. camp &
  build HUD icons). The number row will adjust the depth of these icons, but
  note that most of the UI was already at a good depth in this game out of the
  box and is not adjustable.

Convergence Presets
-------------------
- [: (Default) Sets a good convergence for most of the game (0.4) with the
  crafting book pretty close to the mouse cursor.
- ]: Sets a higher convergence (2.5) that will bring the inventory closer to
  the mouse cursor.

You can save your own custom convergence & separation preset to these buttons.
First, press the button you want to edit, then adjust the convergence and
separation with the standard nVidia keys (Ctrl+F5/F6 if advanced keys are
enabled in the control panel) and finally press F7 to save.

Known Issues
------------
- Glow & sun shafts around the sun & moon is at wrong depth
- Ambient occlusion makes some surfaces appear to shadowed slightly differently
  in each eye. I'd still suggest leaving it on, because it adds a lot of visual
  fidelity to the game. Increasing it to high helps a little.
- Mouse cursor is at screen depth
- The first time the crafting book is opened the tutorial messages are at the
  wrong depth.

Notes
-----
This is an early access game with regular updates, and as such the fix may get
Broken by an update. Please let me know if you see any issues after an update.
