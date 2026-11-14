class Solution {
    private static final String[] ONES = {"", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
        "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"};
    private static final String[] TENS = {"", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"};
    private void chunk(int x, StringBuilder sb) {
        if (x >= 100) { sb.append(' ').append(ONES[x / 100]).append(" Hundred"); x %= 100; }
        if (x >= 20) { sb.append(' ').append(TENS[x / 10]); x %= 10; }
        if (x > 0) sb.append(' ').append(ONES[x]);
    }
    public String numberToWords(int num) {
        if (num == 0) return "Zero";
        int[] values = {1_000_000_000, 1_000_000, 1_000, 1};
        String[] names = {" Billion", " Million", " Thousand", ""};
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 4; i++)
            if (num >= values[i]) { chunk(num / values[i], sb); sb.append(names[i]); num %= values[i]; }
        return sb.toString().trim();
    }
}
