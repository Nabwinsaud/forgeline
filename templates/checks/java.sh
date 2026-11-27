
# --- JVM (Maven / Gradle): __DIR__ ---------------------------------------------
if has_area __AREA__; then
  pushd "__DIR__" >/dev/null
  step "jvm (__DIR__): build · test"
  if [ -x ./gradlew ]; then ./gradlew --no-daemon check
  elif [ -f build.gradle ] || [ -f build.gradle.kts ]; then gradle --no-daemon check
  elif [ -x ./mvnw ]; then ./mvnw -B verify
  else mvn -B verify; fi
  popd >/dev/null
fi
