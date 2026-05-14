#!/bin/bash

# Array of files to test
# Note: kept the spelling "contraints.py" as per your file list
FILES=("src/benchmark.py" "src/contraints.py" "src/main.py" "src/optimizer.py" "src/problem.py")

echo "Starting Python test suite..."
echo "------------------------------"

for FILE in "${FILES[@]}"; do
    if [ -f "$FILE" ]; then
        # Run the python script and suppress output if you just want the success message
        # Remove '>/dev/null 2>&1' if you want to see the actual errors/logs
        python3 "$FILE" > /dev/null 2>&1
        
        if [ $? -eq 0 ]; then
            echo "[PASS] $FILE: success test"
        else
            echo "[FAIL] $FILE: fault detected"
        fi
    else
        echo "[SKIP] $FILE: file not found"
    fi
done

echo "------------------------------"
echo "Tests complete."
