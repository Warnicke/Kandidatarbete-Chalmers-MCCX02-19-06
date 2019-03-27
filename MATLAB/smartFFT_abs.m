function [f,S_o] = smartFFT_abs(S_i,Fs,F_resolution)
%Outputs a frequency vector and the amplitude of a SSB FFT of the signal
%with desired minimum frequency resolution
%   Outputs the amplitude of a single side band FFT and the frequency
%   vector, for a given minimum frequency resolution.


L_seq = length(S_i);
% %Window here
W = window(@flattopwin,L_seq);
S_i = S_i .* W';

%FFT
L_fft = 2 * round (max(Fs/F_resolution,L_seq)/2 )%needed length of FFT, or orignial.
f = Fs*(0:(L_fft/2))/L_fft;

Y = fft(S_i,L_fft);
P2 = abs(Y/L_fft);
P1 = P2(1:L_fft/2+1);
P1(2:end-1) = 2*P1(2:end-1);
S_o = P1;%FFT for delta distance from phase of target



end
