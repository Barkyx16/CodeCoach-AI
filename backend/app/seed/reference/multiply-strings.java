class Solution {
    public String multiply(String a, String b) {
        int n = a.length(), m = b.length();
        int[] res = new int[n + m];
        for (int i = n - 1; i >= 0; i--)
            for (int j = m - 1; j >= 0; j--) {
                int total = (a.charAt(i) - '0') * (b.charAt(j) - '0') + res[i + j + 1];
                res[i + j + 1] = total % 10;
                res[i + j] += total / 10;
            }
        StringBuilder sb = new StringBuilder();
        for (int d : res) if (sb.length() > 0 || d != 0) sb.append(d);
        return sb.length() == 0 ? "0" : sb.toString();
    }
}
