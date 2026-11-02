import java.util.*;

class Solution {
    public int bestTeamScore(int[] scores, int[] ages) {
        int n = scores.length;
        Integer[] order = new Integer[n];
        for (int i = 0; i < n; i++) order[i] = i;
        Arrays.sort(order, (x, y) -> ages[x] != ages[y] ? Integer.compare(ages[x], ages[y]) : Integer.compare(scores[x], scores[y]));
        int[] best = new int[n];
        int answer = 0;
        for (int i = 0; i < n; i++) {
            int si = scores[order[i]];
            best[i] = si;
            for (int j = 0; j < i; j++) if (scores[order[j]] <= si) best[i] = Math.max(best[i], best[j] + si);
            answer = Math.max(answer, best[i]);
        }
        return answer;
    }
}
