import java.util.*;

class Solution {
    public int minMeetingRooms(int[][] meetings) {
        int n = meetings.length;
        int[] starts = new int[n], ends = new int[n];
        for (int i = 0; i < n; i++) { starts[i] = meetings[i][0]; ends[i] = meetings[i][1]; }
        Arrays.sort(starts);
        Arrays.sort(ends);
        int rooms = 0, j = 0;
        for (int s : starts) { if (s >= ends[j]) j++; else rooms++; }
        return rooms;
    }
}
