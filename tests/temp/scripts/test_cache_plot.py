import numpy as np
import matplotlib.pyplot as plt
import os



def get_data(suffix, search_term = "elapsed"):

    files = [f for f in os.listdir(".") if f[-5:] == suffix]
    files = sorted(files, key=lambda a: int(a.split("_")[0]))

    x = []
    y = []
    y_err = []

    for fname in files:
        id = fname.split("_")[0]
        x.append(int(id))
        f = open(fname)
        res = []
        for i in f.readlines():
            if search_term == "elapsed":
                if i.find(search_term) != -1:
                    try:
                        res.append(float(i[:i.find("seconds")].replace(" ", "")))
                    except:
                        print("Cannot convert this line in %s: %s" % (i, fname))
            elif search_term == "insn":
                if i.find(search_term) != -1:
                    try:
                        
                        res.append(float(i[i.find("#    ") + 1:i.find(search_term)].replace(" ", "")))
                    except:
                        print("Cannot convert this line in %s: %s" % (i, fname))
        res = np.array(res)
        y.append(res.mean())
        y_err.append(res.std())

    return x, y, y_err


x, y, y_err = get_data("0.log")
x2, y2, y2_err = get_data("1.log")

plt.figure()
plt.title("Elapsed time (average, std dev)")
plt.xlabel("# processes")
plt.xlabel("seconds")
plt.errorbar(x=x, y=y, yerr=y_err, label="noshared")
plt.errorbar(x=x2, y=y2, yerr=y2_err, label="shared")
plt.legend(loc="best")
plt.grid()
#plt.show()



x, y, y_err = get_data("0.log", search_term="insn")
x2, y2, y2_err = get_data("1.log", search_term="insn")

plt.figure()
plt.title("Instructions per cycle (average, std dev)")
plt.xlabel("# processes")
plt.xlabel("Instructions / cycle")
plt.errorbar(x=x, y=y, yerr=y_err, label="noshared")
plt.errorbar(x=x2, y=y2, yerr=y2_err, label="noshared")
plt.legend(loc="best")
plt.grid()
plt.show()
