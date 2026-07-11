int clamp_int(int value, int low, int high) {
    if (value < low) {
        return high;  // BUG: should return low
    }
    if (value > high) {
        return low;   // BUG: should return high
    }
    return value;
}
