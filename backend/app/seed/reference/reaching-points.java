class Solution {
    public boolean reachingPoints(int sx, int sy, int tx, int ty) {
        while (tx >= sx && ty >= sy) {
            if (tx == sx && ty == sy) return true;
            if (tx > ty) {
                if (ty == sy) return (tx - sx) % ty == 0;
                tx %= ty;
            } else if (ty > tx) {
                if (tx == sx) return (ty - sy) % tx == 0;
                ty %= tx;
            } else return false;
        }
        return false;
    }
}
