#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:?需要Android SDK}}"
BT=$(ls -d "$SDK"/build-tools/* | grep -E '/[0-9]+(\.[0-9]+)*$' | sort -V | tail -1)
PLAT=$(ls -d "$SDK"/platforms/android-* | grep -E '/android-[0-9]+$' | sort -V | tail -1)
JAR="$PLAT/android.jar"
mkdir -p build/gen build/classes build/dex signing
"$BT/aapt2" compile --dir res -o build/res.zip
"$BT/aapt2" link -I "$JAR" --manifest AndroidManifest.xml -o build/base.apk --version-code 10000 --version-name 1.0.0 --min-sdk-version 24 --target-sdk-version 34 --java build/gen build/res.zip
javac --release 8 -classpath "$JAR" -encoding UTF-8 -nowarn -d build/classes $(find src build/gen -name '*.java')
"$BT/d8" --release --min-api 24 --lib "$JAR" --output build/dex $(find build/classes -name '*.class')
cp build/base.apk build/unsigned.apk
(cd build/dex && zip -q -j ../unsigned.apk classes.dex)
"$BT/zipalign" -f -p 4 build/unsigned.apk build/aligned.apk
if [ ! -f signing/debug.keystore ]; then
 keytool -genkeypair -keystore signing/debug.keystore -storepass android -keypass android -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Android Debug,O=Fakao Growth,C=CN"
fi
"$BT/apksigner" sign --ks signing/debug.keystore --ks-pass pass:android --ks-key-alias androiddebugkey --out build/faguan-growth-android.apk build/aligned.apk
"$BT/apksigner" verify build/faguan-growth-android.apk
