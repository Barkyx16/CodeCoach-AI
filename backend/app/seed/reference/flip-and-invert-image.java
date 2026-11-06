class Solution {
    public int[][] flipAndInvertImage(int[][] image) {
        for (int[] row : image) {
            int i = 0, j = row.length - 1;
            while (i <= j) {
                int a = row[i], b = row[j];
                row[i] = 1 - b; row[j] = 1 - a;
                i++; j--;
            }
        }
        return image;
    }
}
