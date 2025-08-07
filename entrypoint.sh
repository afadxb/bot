#!/usr/bin/env bash
while true; do
  python main.py
  sleep $((4 * 60 * 60))
done
