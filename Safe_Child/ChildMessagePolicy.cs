namespace SafeChild;

public sealed record ChildMessageNotice(string Domain, string Message);

public static class ChildMessagePolicy
{
    public static string[] Domains(AppSettings settings, DateTimeOffset now) => settings.IsAllowAllActive(now) ? [] : settings.Domains
        .Where(x => x.ShouldBlock(now) && !string.IsNullOrWhiteSpace(x.ChildMessage))
        .Select(x => x.Domain).Distinct(StringComparer.OrdinalIgnoreCase).ToArray();

    public static ChildMessageNotice? Resolve(AppSettings settings, string url, DateTimeOffset now)
    {
        if (settings.IsAllowAllActive(now) || url.Length > 2048 ||
            !Uri.TryCreate(url, UriKind.Absolute, out var uri) || uri.Scheme is not ("http" or "https") || uri.UserInfo.Length != 0) return null;
        var host = uri.IdnHost.TrimEnd('.');
        var item = settings.Domains.Where(x => x.ShouldBlock(now) && !string.IsNullOrWhiteSpace(x.ChildMessage))
            .OrderByDescending(x => host.Equals(x.Domain, StringComparison.OrdinalIgnoreCase))
            .FirstOrDefault(x => host.Equals(x.Domain, StringComparison.OrdinalIgnoreCase) || host.Equals("www." + x.Domain, StringComparison.OrdinalIgnoreCase));
        return item is null ? null : new ChildMessageNotice(item.Domain, item.ChildMessage);
    }
}
