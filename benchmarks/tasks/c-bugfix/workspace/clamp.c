int clamp_int(int value, int low, int high) {
    if (value < low) {
        return high;
    }
    if (value > high) {
        return low;
    }
    return value;
}
