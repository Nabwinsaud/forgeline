
# --- Ruby: __DIR__ -------------------------------------------------------------
if has_area __AREA__; then
  pushd "__DIR__" >/dev/null
  step "ruby (__DIR__): lint · test"
  bundle install --quiet
  if bundle exec rubocop --version >/dev/null 2>&1; then bundle exec rubocop; fi
  if [ -d spec ]; then bundle exec rspec
  elif [ -f bin/rails ]; then bin/rails test
  elif [ -f Rakefile ]; then bundle exec rake test; fi
  popd >/dev/null
fi
