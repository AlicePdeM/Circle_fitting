import numpy as np

from scipy.optimize import curve_fit, least_squares
from scipy.signal import find_peaks, peak_prominences

from uncertainties import unumpy as unp


def pure_double_lorentzian(f, q0, q1, q_c0, q_c1, f_r0, f_r1, phi0, phi1):

    first_resonnance = 1 - np.exp(1j * phi0) * (q0 / q_c0) / (
        1 - 2j * q0 * (1 - f / f_r0)
    )

    second_resonnance = 1 - np.exp(1j * phi1) * (q1 / q_c1) / (
        1 - 2j * q1 * (1 - f / f_r1)
    )
    return first_resonnance * second_resonnance


def shifted_real_imag_double_lorentzian(
    f, q0, q1, q_c0, q_c1, f_r0, f_r1, phi0, phi1, a, alpha
):
    S = S = (
        pure_double_lorentzian(f, q0, q1, q_c0, q_c1, f_r0, f_r1, phi0, phi1)
        * a
        * np.exp(1j * alpha)
    )
    return np.real(S), np.imag(S)


def real_imag_cost_3(x, y, f, q0, q1, qc0, qc1, f0, f1, phi0, phi1, a, alpha):
    xcalc, ycalc = shifted_real_imag_double_lorentzian(
        f, q0, q1, qc0, qc1, f0, f1, phi0, phi1, a, alpha
    )
    return (xcalc - x) ** 2 + (ycalc - y) ** 2


def double_trouble(f, x, y, S):
    Power = abs(np.fft.fft(x + 1j * y)) ** 2
    Time = np.fft.fftfreq(len(x)) / (np.mean(np.diff(f)))
    FFT_mask = Time < 0
    tau = -Time[FFT_mask][np.argmax(Power[FFT_mask])]

    print(f"tau fft : {tau}")
    peak_indices, _ = find_peaks(-S)

    peak_prominence = peak_prominences(-S, peak_indices)[0]
    ind = np.argsort(-peak_prominence)
    p1 = f[peak_indices[ind[0]]]
    p2 = f[peak_indices[ind[1]]]

    p1_val = S[peak_indices[ind[0]]]
    p2_val = S[peak_indices[ind[1]]]

    if len(ind) > 2:
        p3 = f[peak_indices[ind[2]]]
        p3_val = S[peak_indices[ind[2]]]
        peaks = [p1, p2, p3]

        ind_bis = np.argsort([p1_val, p2_val, p3_val])
        p1 = peaks[ind_bis[0]]
        p2 = peaks[ind_bis[1]]

    if p1 > p2:
        p1, p2 = p2, p1

    delta_f = p2 - p1

    newS_temp = (x + 1j * y) * np.exp(2j * np.pi * tau * f)
    newx_temp = np.real(newS_temp)
    newy_temp = np.imag(newS_temp)

    mask_rough_fit = (p1 - 3 * delta_f) > f
    popt = [0]
    if len(f[mask_rough_fit]) > 20:
        popt, _ = curve_fit(
            lambda f, tau2, b: b - 2 * np.pi * tau2 * f,
            f[mask_rough_fit],
            ydata=np.unwrap(
                np.atan2(newy_temp[mask_rough_fit], newx_temp[mask_rough_fit])
            ),
        )
        tau += popt[0]
    print(tau, popt[0])
    mask = (f > p1 - 2 * delta_f) & (f < p2 + 2 * delta_f)

    newS = newS_temp * np.exp(2j * np.pi * popt[0] * f)

    newS = newS[mask]
    f = f[mask]

    newx = np.real(newS)
    newy = np.imag(newS)

    res = least_squares(
        lambda guess: real_imag_cost_3(newx, newy, f, *guess),
        x0=[1e4, 1e4, 1e4, 1e4, p1, p2, 0, 0, 1, 0],
        bounds=(
            [100 for _ in range(4)] + [min(f), min(f)] + [-np.pi, -np.pi, 0, -np.pi],
            [1e6 for _ in range(4)] + [max(f), max(f)] + [+np.pi, +np.pi, 2, +np.pi],
        ),
    )
    popt = res.x
    J = res.jac
    JTJm1 = np.linalg.inv(np.transpose(J) @ J)
    pcov = JTJm1 * res.cost**2 / (len(f) - 8)

    pstd = np.sqrt(np.diag(pcov))
    if popt[4] > popt[5]:
        popt[:8] = np.flip(np.reshape(popt[:8], shape=[4, 2]), axis=1).flatten()
        pstd[:8] = np.flip(np.reshape(pstd[:8], shape=[4, 2]), axis=1).flatten()

    print(
        f"peaks : 1 : {p1:.5E}, 2 : {p2:.5E} \n popt : 1 : {popt[4]:.5E}, 2 : {popt[5]:.5E} "
    )

    u_q = unp.uarray([popt[0], popt[1]], [pstd[0], pstd[1]])
    u_q_c = unp.uarray([popt[2], popt[3]], [pstd[2], pstd[3]])
    u_phi = unp.uarray([popt[6], popt[7]], [pstd[6], pstd[7]])
    u_q_c = u_q_c * unp.cos(u_phi)
    u_q_i = 1 / ((1 / u_q) - (1 / u_q_c))

    Res1 = np.array(
        [
            [
                popt[8],
                popt[9],
                tau,
                popt[0],
                popt[2],
                popt[6],
                popt[4],
                unp.nominal_values(u_q_i[0]),
            ],
            [
                pstd[8],
                pstd[9],
                0,
                pstd[0],
                pstd[2],
                pstd[6],
                pstd[4],
                unp.std_devs(u_q_i[0]),
            ],
        ]
    )

    Res2 = np.array(
        [
            [
                popt[8],
                popt[9],
                tau,
                popt[1],
                popt[3],
                popt[7],
                popt[5],
                unp.nominal_values(u_q_i[1]),
            ],
            [
                pstd[8],
                pstd[9],
                0,
                pstd[1],
                pstd[3],
                pstd[7],
                pstd[5],
                unp.std_devs(u_q_i[1]),
            ],
        ]
    )
    temp_s2_real, temp_s2_imag = shifted_real_imag_double_lorentzian(f, *popt)
    return (
        [Res1, Res2],
        (newx, newy, 0, 0, 0),
        (f, abs(newS), (temp_s2_real**2 + temp_s2_imag**2) ** 0.5),
    )


def Z_Z0_phi(f, Q_c, Q_i, f_r, phi):
    dw = (f - f_r) / f_r
    return Q_c * np.exp(1j * phi) * (1 / Q_i + 2j * dw)


def true_shifted_double_lorentzian(f, qc0, qc1, qi0, qi1, f0, f1, phi, a, alpha):
    A = Z_Z0_phi(f, qc0, qi0, f0, phi)
    B = Z_Z0_phi(f, qc1, qi1, f1, phi)
    return a * np.exp(1j * alpha) / (1 + 1 / A + 1 / B)


def real_imag_cost_4(x, y, f, qc0, qc1, qi0, qi1, f0, f1, phi, a, alpha):
    S = true_shifted_double_lorentzian(f, qc0, qc1, qi0, qi1, f0, f1, phi, a, alpha)
    return (x - np.real(S)) ** 2 + (y - np.imag(S)) ** 2


def true_double_trouble(f, x, y, S):
    Power = abs(np.fft.fft(x + 1j * y)) ** 2
    Time = np.fft.fftfreq(len(x)) / (np.mean(np.diff(f)))
    FFT_mask = Time < 0
    tau = -Time[FFT_mask][np.argmax(Power[FFT_mask])]

    print(f"tau fft : {tau}")
    peak_indices, _ = find_peaks(-S)

    peak_prominence = peak_prominences(-S, peak_indices)[0]
    ind = np.argsort(-peak_prominence)
    p1 = f[peak_indices[ind[0]]]
    p2 = f[peak_indices[ind[1]]]

    p1_val = S[peak_indices[ind[0]]]
    p2_val = S[peak_indices[ind[1]]]

    if len(ind) > 2:
        p3 = f[peak_indices[ind[2]]]
        p3_val = S[peak_indices[ind[2]]]
        peaks = [p1, p2, p3]

        ind_bis = np.argsort([p1_val, p2_val, p3_val])
        p1 = peaks[ind_bis[0]]
        p2 = peaks[ind_bis[1]]

    if p1 > p2:
        p1, p2 = p2, p1

    delta_f = p2 - p1

    newS_temp = (x + 1j * y) * np.exp(2j * np.pi * tau * f)
    newx_temp = np.real(newS_temp)
    newy_temp = np.imag(newS_temp)

    mask_rough_fit = (p1 - 3 * delta_f) > f
    popt = [0]
    if len(f[mask_rough_fit]) > 20:
        popt, _ = curve_fit(
            lambda f, tau2, b: b - 2 * np.pi * tau2 * f,
            f[mask_rough_fit],
            ydata=np.unwrap(
                np.atan2(newy_temp[mask_rough_fit], newx_temp[mask_rough_fit])
            ),
        )
        tau += popt[0]
    print(tau, popt[0])
    mask = (f > p1 - 2 * delta_f) & (f < p2 + 2 * delta_f)

    newS = newS_temp * np.exp(2j * np.pi * popt[0] * f)

    newS = newS[mask]
    f = f[mask]

    newx = np.real(newS)
    newy = np.imag(newS)

    res = least_squares(
        lambda guess: real_imag_cost_4(newx, newy, f, *guess),
        x0=[1e4, 1e4, 1e4, 1e4, p1, p2, 0, 1, 0],
        bounds=(
            [100 for _ in range(4)] + [min(f), min(f)] + [-np.pi, 0, -np.pi],
            [1e6 for _ in range(4)] + [max(f), max(f)] + [+np.pi, 2, +np.pi],
        ),
    )
    popt = res.x
    J = res.jac
    JTJm1 = np.linalg.inv(np.transpose(J) @ J)
    pcov = JTJm1 * res.cost**2 / (len(f) - 7)

    pstd = np.sqrt(np.diag(pcov))
    if popt[4] > popt[5]:
        print("switch happened")
        popt[:6] = np.flip(np.reshape(popt[:6], shape=[3, 2]), axis=1).flatten()
        pstd[:6] = np.flip(np.reshape(pstd[:6], shape=[3, 2]), axis=1).flatten()

    print(
        f"peaks : 1 : {p1:.5E}, 2 : {p2:.5E} \n popt : 1 : {popt[4]:.5E}, 2 : {popt[5]:.5E} "
    )

    u_q_c = unp.uarray([popt[0], popt[1]], [pstd[0], pstd[1]])
    u_q_i = unp.uarray([popt[2], popt[3]], [pstd[2], pstd[3]])
    u_phi = unp.uarray([popt[6], popt[6]], [pstd[6], pstd[6]])
    u_q_c = u_q_c * unp.cos(u_phi)
    u_q = 1 / ((1 / u_q_i) + (1 / u_q_c))

    Res1 = np.array(
        [
            [
                popt[7],
                popt[8],
                tau,
                unp.nominal_values(u_q[0]),
                popt[0],
                popt[6],
                popt[4],
                popt[2],
            ],
            [
                pstd[7],
                pstd[8],
                0,
                unp.std_devs(u_q[0]),
                pstd[0],
                pstd[6],
                pstd[4],
                pstd[2],
            ],
        ]
    )

    Res2 = np.array(
        [
            [
                popt[7],
                popt[8],
                tau,
                unp.nominal_values(u_q[1]),
                popt[1],
                popt[7],
                popt[5],
                popt[3],
            ],
            [
                pstd[7],
                pstd[8],
                0,
                unp.std_devs(u_q[1]),
                pstd[1],
                pstd[7],
                pstd[5],
                pstd[3],
            ],
        ]
    )
    temp_s2_real, temp_s2_imag = shifted_real_imag_double_lorentzian(f, *popt)
    return (
        [Res1, Res2],
        (newx, newy, 0, 0, 0),
        (f, abs(newS), (temp_s2_real**2 + temp_s2_imag**2) ** 0.5),
    )
