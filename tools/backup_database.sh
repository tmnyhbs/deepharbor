#!/usr/bin/env bash

# This backs up the PostgreSQL database to a file named with the current 
# date and moves it to a backup location.
# It assumes that pg_dump is installed and that the database is accessible.
# on localhost with the username and password set below.
# Note that you need to use the same version of the tools as the database!

export PGUSER=dh
export PGPASSWORD=dh
export WORKING_DIR=/home/rolson/temp
export CURRENT_DATE=`date +"%Y-%m-%d_%H-%M-%S"`
export DATABASE=deepharbor
export BACKUP_FILE=$DATABASE_$CURRENT_DATE.dump
export BACKUP_LOCATION=$WORKING_DIR/backups
export PROG_LOCATION=/usr/bin

pushd $WORKING_DIR
echo Creating $DATABASE database dump for $CURRENT_DATE
$PROG_LOCATION/pg_dump -h localhost -c -C -Fc $DATABASE > $WORKING_DIR/$BACKUP_FILE
echo Moving $BACKUP_FILE to $BACKUP_LOCATION
mv $WORKING_DIR/$BACKUP_FILE $BACKUP_LOCATION
popd

unset PGPASSWORD
