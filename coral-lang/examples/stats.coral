// stats.coral — Python library integration example
// Uses numpy for statistics on a typed Coral dataset

import numpy as np;

public class Dataset {
    private str         label;
    private list<float> values;

    public void __init__(str label, list<float> values) {
        self.label  = label;
        self.values = values;
    }

    public float mean()   { return np.mean(self.values);  }
    public float median() { return np.median(self.values); }
    public float std()    { return np.std(self.values);    }
    public float minVal() { return np.min(self.values);    }
    public float maxVal() { return np.max(self.values);    }

    public int countAbove(float threshold) {
        int tally = 0;
        foreach(float v in self.values) {
            if(v > threshold) {
                tally++;
            }
        }
        return tally;
    }

    public list<float> normalise() {
        float mn  = self.minVal();
        float mx  = self.maxVal();
        float rng = mx - mn;
        list<float> out = [];
        foreach(float v in self.values) {
            out.append(round((v - mn) / rng, 4));
        }
        return out;
    }

    public void report() {
        print("─────────────────────────────");
        print("Dataset : " + self.label);
        print("N       : " + str(len(self.values)));
        print("Mean    : " + str(round(self.mean(),   3)));
        print("Median  : " + str(round(self.median(), 3)));
        print("Std dev : " + str(round(self.std(),    3)));
        print("Min     : " + str(self.minVal()));
        print("Max     : " + str(self.maxVal()));
        print("─────────────────────────────");
    }
}

public void main() {
    list<float> temps = [
        12.4, 15.1, 11.8, 17.2, 19.5,
        22.0, 24.3, 23.7, 20.1, 16.8,
        13.2, 10.9
    ];

    Dataset monthly = new Dataset("Monthly Temperatures (°C)", temps);
    monthly.report();

    int hotMonths = monthly.countAbove(18.0);
    print("Months above 18°C : " + str(hotMonths));

    list<float> norm = monthly.normalise();
    print("Normalised        : " + str(norm));

    // Numpy operations directly on Coral list<float>
    list<float> arr      = np.array(temps);
    float       variance = np.var(arr);
    list<float> cumsum   = np.cumsum(arr).tolist();

    print("Variance          : " + str(round(variance, 3)));
    print("Cumulative sum    : " + str([round(v, 1) for v in cumsum]));
}

main();
