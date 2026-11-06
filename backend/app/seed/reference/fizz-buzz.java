class Solution {
    public String[] fizzBuzz(int n) {
        String[] out = new String[n];
        for (int i = 1; i <= n; i++)
            out[i - 1] = i % 15 == 0 ? "FizzBuzz" : i % 3 == 0 ? "Fizz" : i % 5 == 0 ? "Buzz" : String.valueOf(i);
        return out;
    }
}
