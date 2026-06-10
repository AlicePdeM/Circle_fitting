import numpy as np
import uncertainties as u

from scipy.linalg import eig
from scipy.differentiate import jacobian
from scipy.optimize import curve_fit, least_squares


def manual_unwrap_decreasing(angles, threshold=np.pi):
    unwrapped = np.copy(angles)
    # flag = False
    for i in range(1, len(unwrapped)):
        diff = unwrapped[i] - unwrapped[i - 1]
        # If the jump is larger than the threshold, unwrap it
        if diff > threshold:
            # Check if the jump is positive or negative
            unwrapped[i:] -= 2 * np.pi
            break

    return unwrapped


def circle_fit(x_i, y_i):

    z_i = x_i**2 + y_i**2
    n_i = np.ones_like(x_i)

    L = [z_i, x_i, y_i, n_i]

    M = np.array([[np.sum(alpha * beta) for beta in L] for alpha in L])
    B = np.array(
        [
            [0, 0, 0, -2],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [-2, 0, 0, 0],
        ]
    )

    evals, evecs = eig(M, B)
    evals = np.real(evals)
    # print(evals,evecs)
    v = evecs[:, np.argmin(abs(evals))]

    x_c_calc = -v[1] / (2 * v[0])
    y_c_calc = -v[2] / (2 * v[0])
    r_c_calc = (v[1] ** 2 + v[2] ** 2 - 4 * v[0] * v[3]) ** 0.5 / (2 * abs(v[0]))

    return (x_c_calc, y_c_calc, r_c_calc)


def lorentzian(f, a, alpha, tau, q, q_c, phi, f_r):
    Res = []
    for frequency in f:
        S21_pure = 1 - (
            (q / q_c) * np.exp(1j * phi) / (1 - 2j * q * (1 - frequency / f_r))
        )
        S_environment = a * np.exp(1j * (alpha - 2 * np.pi * frequency * tau))
        Res.append(S21_pure * S_environment)
    return np.array(Res)


def random_lorentzian(n, sigma):
    # ideal resonator
    f_r = 10000 + 5000 * np.random.random()
    df_r = np.random.random() / 2 + 0.5
    q_c = 10**4
    q = f_r / df_r
    phi = np.random.random() * np.pi / 3 - np.pi / 6

    real_q_c = np.real(q_c * np.exp(1j * phi))
    qi = 1 / (real_q_c**-1 + q**-1)

    # environment effect
    a = 0.5 + np.random.random() / 2
    alpha = np.random.random() * 2 * np.pi
    tau = 0.1 + 0.9 * np.random.random()

    f = np.linspace(f_r - 2 * df_r, f_r + 2 * df_r, n)

    S21 = lorentzian(f, a, alpha, tau, q, q_c, phi, f_r) + (
        np.random.normal(0, sigma, n) + 1j * np.random.normal(0, sigma, n)
    )
    return (
        (f, np.real(S21), np.imag(S21), np.abs(S21)),
        (f_r, df_r, q_c, q, qi, phi),
        (a, alpha, tau),
    )


def least_square_circle(tau, f, S):
    new_S = S * np.exp(2j * np.pi * f * tau)
    nx = np.real(new_S)
    ny = np.imag(new_S)
    x_c, y_c, r_c = circle_fit(nx, ny)
    # print(tau,x_c,y_c,r_c)
    # print(np.sum((r_c**2) - (x_i-x_c)**2 - (y_i-y_c)**2))
    return abs(((r_c**2) - (nx - x_c) ** 2 - (ny - y_c) ** 2))


def lorent_residue(wrap, f, S):
    a, alpha, tau, q, q_c, phi, f_r = wrap
    # print(a, alpha, tau, q, q_c, phi, f_r)
    Res = []
    Lor = lorentzian(f, a, alpha, tau, q, q_c, phi, f_r)
    for i, y in enumerate(S):
        Res.append(np.abs(y - Lor[i]))

    return np.array(Res)


def rough_fit(frequency, tau, b):  # affine function
    return -2 * np.pi * frequency * tau + b


def phase_frequency(f, theta0, q_l, f_r):
    # print(theta0, q_l, f_r)
    return theta0 - 2 * np.arctan(2 * q_l * (1 - f / f_r))


def rough_estimate_tau(f, x, y):
    uw = manual_unwrap_decreasing(np.atan2(y, x), np.pi / 2)
    popt, pocv = curve_fit(
        lambda x, a, b: b - 2 * np.pi * x * a,
        xdata=f,
        ydata=uw,
    )
    return popt[0]


def cable_delay(frequencies, x, y, f_resonnance=np.inf, df_resonnance=0, tau=0):

    S = x + 1j * y

    # rough affine fit on the phase
    if tau == 0:
        print("estimating tau")
        rough_mask = (
            frequencies < f_resonnance - df_resonnance
        )  # Near the resonnance, affine approx is wrong
        tau = rough_estimate_tau(frequencies[rough_mask], x[rough_mask], y[rough_mask])

    # fit of tau based on circle fitting the results
    result = least_squares(
        lambda x: least_square_circle(x, frequencies, S),
        tau,
        method="dogbox",
        loss="soft_l1",  # To be fair, neither method nor loss does matter, those are just infinitesimaly better
    )
    # print(result)
    return result.x[0]


def rough_resonnance(f, S: np.ndarray):

    absS = np.abs(S)
    f_r_estimate = f[np.argmin(absS)]
    base_level = np.mean(absS)
    half_heigth = (base_level + np.min(absS)) / 2

    i_ref = absS.tolist().index(min(absS))
    print(i_ref)

    i_bef = np.where(
        absS == min(absS[f < f_r_estimate], key=lambda u: abs(u - half_heigth))
    )[0][0]

    if i_ref - i_bef < 10:
        i_bef = i_ref - 10
        print("left re-calibration defaulted")
    f_bef = f[i_bef]

    i_aft = np.where(
        absS == min(absS[f > f_r_estimate], key=lambda u: abs(u - half_heigth))
    )[0][0]
    if i_aft - i_ref < 10:
        i_aft = i_ref + 10
        print("right re-calibration defaulted")
    f_aft = f[i_aft]

    df_r = abs(f_aft - f_bef)
    return f_r_estimate, df_r


def lor_circle_fit(f, x, y, pre_calc_tau=0):
    S = x + 1j * y
    f_r_estimate, df_r_estimate = rough_resonnance(f, S)

    mask = (f > f_r_estimate - 2 * df_r_estimate) & (
        f < f_r_estimate + 2 * df_r_estimate
    )
    # Finding tau
    f = f[mask]
    x = x[mask]
    y = y[mask]
    S = S[mask]

    tau = cable_delay(f, x, y, f_r_estimate, df_r_estimate, pre_calc_tau)

    newS = S * np.exp(2j * np.pi * f * tau)
    newx = np.real(newS)
    newy = np.imag(newS)

    x_c, y_c, r_c = circle_fit(newx, newy)
    newx_centered = newx - x_c
    newy_centered = newy - y_c
    newS_centered = newx_centered + 1j * newy_centered
    # (now we have a centered circle, with a hole)

    # First normalisation

    new_uw_phase = manual_unwrap_decreasing(
        np.atan2(newy_centered, newx_centered), np.pi / 2
    )
    initial_guess = [(max(new_uw_phase) - min(new_uw_phase)) / 2, -1e4, 1]
    popt, pocv = curve_fit(
        phase_frequency, f / f_r_estimate, new_uw_phase, p0=initial_guess
    )
    popt[2] *= f_r_estimate
    f_r_estimate = popt[2]  # this operation gives us a better estomate for f_r

    beta = popt[0] + np.pi

    transfo = x_c + r_c * np.cos(beta) + 1j * (y_c + r_c * np.sin(beta))

    # Recuperation of values
    a = abs(transfo)
    alpha = np.atan2(
        np.imag(transfo), np.real(transfo)
    )  # alpha is always wrong but it doesn't matter

    # Canonical form of lorentzian
    newS_transformed = newS / transfo
    newx_transformed = np.real(newS_transformed)
    newy_transformed = np.imag(newS_transformed)

    nx_c, ny_c, nr_c = circle_fit(newx_transformed, newy_transformed)

    phi_fit = -np.arcsin(ny_c / nr_c)

    # recalculation of f_r and Q based of known value of phi (phi_fit)

    new_transformed_uw_phase = manual_unwrap_decreasing(
        np.atan2(newy_transformed - ny_c, newx_transformed - nx_c), np.pi / 2
    )
    # print(new_transformed_uw_phase)
    initial_guess = [popt[1], 1]
    popt, pocv = curve_fit(
        lambda x, q, f: phase_frequency(x, phi_fit - np.pi, q, f),
        f / f_r_estimate,
        new_transformed_uw_phase,
        p0=initial_guess,
    )
    # popt[1] *= f_r_estimate

    q = -popt[0]
    f_r = popt[1] * f_r_estimate
    q_c = abs(np.exp(1j * phi_fit) * q / (2 * nr_c))

    # Uncertainties
    J = jacobian(
        lambda x: lorent_residue(x, f, S), (a, alpha, tau, q, q_c, phi_fit, f_r)
    )
    JTJm1 = np.linalg.inv(np.transpose(J.df) @ J.df)

    sigma2 = (
        JTJm1
        * np.sum(lorent_residue((a, alpha, tau, q, q_c, phi_fit, f_r), f, S) ** 2)
        / (len(f) - 7)  # 7 because seven variables
    )
    sigma = np.diagonal(sigma2) ** 0.5
    u_q = u.ufloat(q, sigma[3])
    u_q_c = u.ufloat(abs(q_c * np.exp(1j * phi_fit)), sigma[4])
    u_q_i = 1 / ((1 / u_q) - (1 / u_q_c))

    Res = np.array(
        [
            [a, alpha, tau, q, q_c, phi_fit, f_r, u.nominal_value(u_q_i)],
            [
                sigma[0],
                sigma[1],
                sigma[2],
                sigma[3],
                sigma[4],
                sigma[5],
                sigma[6],
                u.std_dev(u_q_i),
            ],
        ]
    )
    # print(Res)
    return (
        Res,
        (newx, newy, x_c, y_c, r_c),
        (
            f,
            new_transformed_uw_phase,
            phase_frequency(f / f_r_estimate, phi_fit - np.pi, *popt),
        ),
    )
