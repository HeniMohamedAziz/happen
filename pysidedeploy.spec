[app]
title = Happen
project_dir = .
input_file = main.py
exec_directory = dist
project_file = 
icon = assets/happen.ico

[python]
python_path = 
packages = Nuitka==4.1.1
android_packages = buildozer==1.5.0,cython==0.29.33

[qt]
qml_files = 
excluded_qml_plugins = 
modules = Core,Gui,Widgets
plugins = accessiblebridge,egldeviceintegrations,generic,iconengines,imageformats,platforminputcontexts,platforms,platforms/darwin,platformthemes,styles,wayland-decoration-client,wayland-graphics-integration-client,wayland-shell-integration,xcbglintegrations

[android]
wheel_pyside = 
wheel_shiboken = 
plugins = 

[nuitka]
macos.permissions = 
mode = onefile
extra_args = --quiet --noinclude-qt-translations --windows-console-mode=disable --include-data-files=assets/happen.ico=assets/happen.ico

[buildozer]
mode = debug
recipe_dir = 
jars_dir = 
ndk_path = 
sdk_path = 
local_libs = 
arch = 
