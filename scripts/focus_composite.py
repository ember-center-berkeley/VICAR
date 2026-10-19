"""Shared soft-edged focus treatment for the summary and ladder human video."""
import numpy as np
from scipy.ndimage import maximum_filter, gaussian_filter
from PIL import Image, ImageFilter, ImageChops


def soft_focus(crop, matte, scale=1., blur_radius=None, floor_start=.79):
    """Preserve subject detail with a broad, continuous transition to defocus.

    `scale` is relative to the 920-pixel summary panel. The background-only
    convolution avoids foreground-color halos; the wider feather softens the
    join instead of blurring the whole subject.
    """
    w,h=crop.size
    pad=max(3,int(round(3*scale))|1)
    core=Image.fromarray(maximum_filter(np.asarray(matte),size=pad,mode='nearest'))
    alpha=core.filter(ImageFilter.GaussianBlur(7*scale))
    # A gentle gain restores solid interiors while retaining the broad feather.
    alpha=alpha.point(lambda value:min(255,round(value*1.12)))
    small=(max(1,w//2),max(1,h//2))
    rgb=np.asarray(crop.resize(small,Image.Resampling.BILINEAR),dtype=np.float32)
    weight=1-np.asarray(core.resize(small,Image.Resampling.BILINEAR),dtype=np.float32)/255
    radius=(8*scale if blur_radius is None else blur_radius)/2
    # Keep convolution and normalization in float. Quantizing the tiny weights
    # near silhouettes before dividing creates jagged bright/dark edge pixels.
    numerator=gaussian_filter(rgb*weight[:,:,None],sigma=(radius,radius,0),mode='nearest')
    denominator=gaussian_filter(weight,sigma=radius,mode='nearest')
    blurred=np.where((denominator>1e-4)[:,:,None],numerator/np.maximum(1e-4,denominator[:,:,None]),rgb)
    blurred=Image.fromarray(np.uint8(np.clip(blurred,0,255))).resize((w,h),Image.Resampling.BILINEAR)
    # A gradual focus falloff on the floor avoids a hard horizontal seam.
    yy=np.arange(h)/h
    floor=np.clip((yy-floor_start)/(1-floor_start-.02),0,1)**2*.92
    floor=Image.fromarray(np.uint8(np.broadcast_to(floor[:,None]*255,(h,w))))
    alpha=ImageChops.lighter(alpha,floor)
    return Image.composite(crop,blurred,alpha),alpha
