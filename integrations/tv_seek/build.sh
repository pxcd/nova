#!/bin/sh
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
build="$repo/.local/tv-helper-build"
JDK_HOME=${JDK_HOME:-"$build/jdk/Contents/Home"}
ANDROID_JAR=${ANDROID_JAR:-"$build/android.jar"}
R8_JAR=${R8_JAR:-"$build/r8-8.3.37.jar"}
mkdir -p "$build/classes" "$build/dex"
"$JDK_HOME/bin/javac" --release 8 -classpath "$ANDROID_JAR" -d "$build/classes" "$repo/integrations/tv_seek/NovaSeek.java"
"$JDK_HOME/bin/java" -cp "$R8_JAR" com.android.tools.r8.D8 --release --min-api 31 --lib "$ANDROID_JAR" --output "$build/dex" "$build/classes/NovaSeek.class"
"$JDK_HOME/bin/jar" --create --file "$build/nova-seek.jar" -C "$build/dex" classes.dex
