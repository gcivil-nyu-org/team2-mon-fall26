#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

# Only the isolated Compose database gets a test-schema grant. The web service
# never receives the root password and uses its normal application user.
docker compose exec -T db sh -eu -c '
  case "$MYSQL_DATABASE:$MYSQL_USER" in
    *[!a-zA-Z0-9_:]*|:*) echo "Use letters, numbers and underscores for database/user names." >&2; exit 1 ;;
  esac
  test_database=$(printf "test_%s" "$MYSQL_DATABASE" | sed "s/_/\\\\_/g")
  MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --user=root --execute="GRANT ALL PRIVILEGES ON \`$test_database\`.* TO '\''$MYSQL_USER'\''@'\''%'\'';"
'

docker compose exec -T web python manage.py test --noinput "$@"
