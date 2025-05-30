# Muse Scripting

**Fix Image**
Static Variables
  - DO_NOTHING: If enabled, function will return the exact image it's given, useful for testing
  - WHITE_THRESHOLD: The saturation value for a pixel above it to be considered white background & removed
  - BLACK_THRESHOLD: The saturation value for a pixel below it to be considered black & left alone during inversion

Script
  - fix_image is a helper function to apply a variety of manipulations to your image
  - It can be ran standalone and asks the user for a directory, where it will "fix" all artwork in-place

**Automatic LAP Creation**
Static Variables
  - IS_BETA: If enabled, uses beta.fslaser.com for all operations, if not, defaults to re4.fslaser.com
  - LASER_FOLDER_PATH: The path to the folder where laser shenanigans will take place
  - DEVICE_ACCESS_CODE: The access code to your specific Muse, shown on its screen
  - SLEEP_TIME: Time, in seconds, to sleep before scanning directory for input PNGs again

Script
  - automatic_lap_creation is the main script that watches a directory and turns its PNGs into LAPs, to be sent to your Muse
  - It does a small amount of manipulation to attempt to center your image as best as possible in your Muse/RE4 workspace
  - It scales the image to RE4's forced 96DPI, assuming an input DPI of 300

**Run LAP Job (GUI)**
Static Variables
  - IS_BETA: If enabled, uses beta.fslaser.com for all operations, if not, defaults to re4.fslaser.com
  - LASER_FOLDER_PATH: The path to the folder where laser shenanigans will take place
  - DEVICE_ACCESS_CODE: The access code to your specific Muse, shown on its screen
  - SLEEP_TIME: Time, in seconds, to sleep before sending LAP job to FSL endpoint

Script:
  - Opens a small GUI for use with barcode scanners
  - It counts down from SLEEP_TIME and then starts a job



# To Do
  - Ping FSL endpoint to stop job once completed