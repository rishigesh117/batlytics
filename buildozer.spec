[app]

# App metadata
title = Batlytics
package.name = batlytics
package.domain = com.batlytics
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,db
version = 1.1.0

# Application requirements
requirements = python3,kivy,plyer,pyjnius,android,reportlab

# Android settings
android.permissions = RECORD_AUDIO,INTERNET
# (int) Target Android API, should be as high as possible.
android.api = 35

# (int) Minimum API your APK / AAB will support.
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a

# App orientation (portrait for cricket scoring)
orientation = portrait

# Fullscreen mode
fullscreen = 0

# Icon and presplash (will use defaults if not provided)
icon.filename = logo.png
# presplash.filename = assets/presplash.png

# Android specific
android.accept_sdk_license = True

# iOS settings (if needed later)
ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master

# Log level
log_level = 2

[buildozer]
log_level = 2
warn_on_root = 0
