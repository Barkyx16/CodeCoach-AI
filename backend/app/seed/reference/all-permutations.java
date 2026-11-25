import java.util.*;

class Solution {
    private void build(int[] nums, boolean[] used, List<Integer> path, List<int[]> out) {
        if (path.size() == nums.length) { out.add(path.stream().mapToInt(Integer::intValue).toArray()); return; }
        for (int i = 0; i < nums.length; i++) {
            if (used[i]) continue;
            used[i] = true;
            path.add(nums[i]);
            build(nums, used, path, out);
            path.remove(path.size() - 1);
            used[i] = false;
        }
    }
    public int[][] permute(int[] nums) {
        Arrays.sort(nums);
        List<int[]> out = new ArrayList<>();
        build(nums, new boolean[nums.length], new ArrayList<>(), out);
        return out.toArray(new int[0][]);
    }
}
