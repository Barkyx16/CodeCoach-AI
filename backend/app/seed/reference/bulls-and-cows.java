class Solution {
    public String getHint(String secret, String guess) {
        int bulls = 0, cows = 0;
        int[] cs = new int[10], cg = new int[10];
        for (int i = 0; i < secret.length(); i++) {
            char a = secret.charAt(i), b = guess.charAt(i);
            if (a == b) bulls++;
            else { cs[a - '0']++; cg[b - '0']++; }
        }
        for (int d = 0; d < 10; d++) cows += Math.min(cs[d], cg[d]);
        return bulls + "A" + cows + "B";
    }
}
